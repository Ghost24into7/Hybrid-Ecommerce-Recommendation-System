from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import bcrypt
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

app = Flask(__name__)
app.secret_key = ''  # Replace with a secure secret key
app.config['MONGO_URI'] = ''  # Replace with your MongoDB URI
mongo = PyMongo(app)

# Password verification logic
def verify_password(password):
    if len(password) < 12 or not any(char.islower() for char in password):
        return False
    if not any(char.isupper() for char in password) or not any(char.isdigit() for char in password):
        return False
    if not any(char in "!@#$%^&*()-_+=<>?/" for char in password):
        return False
    return True

# Fetch generic recommendations
def get_generic_recommendations():
    popular_products = list(mongo.db.products.aggregate([
        {"$lookup": {"from": "ratings", "localField": "_id", "foreignField": "product_id", "as": "ratings"}},
        {"$addFields": {"avg_rating": {"$avg": "$ratings.rating"}, "rating_count": {"$size": "$ratings"}}},
        {"$sort": {"rating_count": -1, "avg_rating": -1}},
        {"$limit": 6}
    ]))
    return popular_products

# Fetch new products
def get_new_products():
    recent_products = list(mongo.db.products.find(
        {"created_at": {"$gte": pd.Timestamp.now() - pd.Timedelta(days=30)}},
        {"_id": 1, "product_name": 1, "description": 1, "tags": 1, "price": 1}
    ).limit(6))
    return recent_products

# Fetch recommendations (Hybrid Filtering)
def fetch_recommendations(user_id):
    user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_data:
        return []

    user_purchases = user_data.get('purchased_products', [])
    product_list = list(mongo.db.products.find())
    product_df = pd.DataFrame(product_list)

    recommendations = []

    if not user_purchases:
        return get_generic_recommendations() + get_new_products()

    if not product_df.empty:
        product_df['tags'] = product_df['tags'].apply(lambda x: ','.join(x) if isinstance(x, list) else '')
        product_df['content_features'] = product_df['tags'] + ' ' + product_df['description'].fillna('')

        tfidf_vectorizer = TfidfVectorizer()
        tfidf_matrix = tfidf_vectorizer.fit_transform(product_df['content_features'])
        cosine_sim = cosine_similarity(tfidf_matrix)

        similar_users = mongo.db.users.find({"purchased_products": {"$in": user_purchases}})
        for user in similar_users:
            for product in user.get('purchased_products', []):
                if product not in user_purchases and product not in recommendations:
                    product_details = mongo.db.products.find_one({"_id": ObjectId(product)})
                    if product_details:
                        recommendations.append(product_details)

        user_product_indices = product_df[product_df['_id'].isin(user_purchases)].index.tolist()
        if user_product_indices:
            similar_indices = cosine_sim[user_product_indices].argsort(axis=1)[:, -6:].flatten()
            for idx in similar_indices:
                recommended_product = product_df.iloc[idx]
                if recommended_product['_id'] not in user_purchases and recommended_product['_id'] not in recommendations:
                    recommendations.append(mongo.db.products.find_one({"_id": recommended_product['_id']}))

    return recommendations[:6]

# Submit product rating
def submit_rating(user_id, product_id, rating):
    if not (1 <= rating <= 5):
        return False

    rating_entry = {
        "user_id": user_id,
        "product_id": product_id,
        "rating": rating
    }

    existing_rating = mongo.db.ratings.find_one({"user_id": user_id, "product_id": product_id})
    if existing_rating:
        mongo.db.ratings.update_one({"_id": existing_rating["_id"]}, {"$set": {"rating": rating}})
    else:
        mongo.db.ratings.insert_one(rating_entry)

    return True

# All Flask routes
@app.route('/')
def index():
    recommendations = fetch_recommendations(session['user_id']) if 'user_id' in session else []
    return render_template('index.html', recommendations=recommendations)

@app.route('/product_list')
def product_list():
    products = list(mongo.db.products.find())
    recommendations = fetch_recommendations(session['user_id']) if 'user_id' in session else []
    return render_template('product_list.html', products=products, recommendations=recommendations)

@app.route('/product/<product_id>', methods=['GET', 'POST'])
def product_detail(product_id):
    product = mongo.db.products.find_one({"_id": ObjectId(product_id)})
    if product is None:
        return "Product not found", 404

    if request.method == 'POST':
        rating = int(request.form['rating'])
        if 'user_id' in session:
            submit_rating(session['user_id'], product_id, rating)
            flash('Rating submitted successfully!', 'success')
        else:
            flash('You need to log in to submit a rating.', 'warning')

    recommendations = fetch_recommendations(session['user_id']) if 'user_id' in session else []
    return render_template('product_detail.html', product=product, recommendations=recommendations)

@app.route('/cart')
def cart():
    cart_items = []
    total_price = 0
    if 'user_id' in session:
        user_cart = mongo.db.users.find_one({"_id": ObjectId(session['user_id'])}).get('cart', [])
        cart_items = list(mongo.db.products.find({"_id": {"$in": [ObjectId(item) for item in user_cart]}}))
        total_price = sum(item['price'] for item in cart_items)

    recommendations = fetch_recommendations(session['user_id']) if 'user_id' in session else []
    return render_template('cart.html', cart_items=cart_items, total_price=total_price, recommendations=recommendations)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.json['product_id']
    if 'user_id' in session:
        mongo.db.users.update_one({"_id": ObjectId(session['user_id'])}, {"$push": {"cart": product_id}})
        cart_count = len(mongo.db.users.find_one({"_id": ObjectId(session['user_id'])})['cart'])
        return jsonify(success=True, cart_count=cart_count)
    return jsonify(success=False)

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    product_id = request.json['product_id']
    if 'user_id' in session:
        mongo.db.users.update_one({"_id": ObjectId(session['user_id'])}, {"$pull": {"cart": product_id}})
        return jsonify(success=True)
    return jsonify(success=False)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        shipping_address = request.form['shipping_address']
        user_cart = mongo.db.users.find_one({"_id": ObjectId(session['user_id'])}).get('cart', [])

        if user_cart:
            cart_items = list(mongo.db.products.find({"_id": {"$in": [ObjectId(item) for item in user_cart]}}))

            order = {
                "user_id": session['user_id'],
                "products": cart_items,
                "shipping_address": shipping_address,
                "total_price": sum(item['price'] for item in cart_items),
                "status": "Pending",
                "order_date": pd.Timestamp.now()
            }

            mongo.db.orders.insert_one(order)

            purchased_product_ids = [str(item['_id']) for item in cart_items]

            mongo.db.users.update_one(
                {"_id": ObjectId(session['user_id'])},
                {"$addToSet": {"purchased_products": {"$each": purchased_product_ids}}, "$set": {"cart": []}}
            )

            flash('Order placed successfully!', 'success')
            return redirect(url_for('index'))

        else:
            flash('Your cart is empty!', 'warning')

    return render_template('checkout.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = mongo.db.users.find_one({"username": username})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['user_id'] = str(user['_id'])
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/rate_product/<product_id>', methods=['POST'])
def rate_product(product_id):
    if 'user_id' not in session:
        flash('You need to log in to rate a product.', 'warning')
        return redirect(url_for('login'))

    rating = request.form.get('rating')
    if not rating or not rating.isdigit() or not (1 <= int(rating) <= 5):
        flash('Invalid rating. Please provide a rating between 1 and 5.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    user_id = session['user_id']
    submit_rating(user_id, product_id, int(rating))
    flash('Thank you for rating this product!', 'success')
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match.', 'warning')
        elif not verify_password(password):
            flash('Password does not meet the security requirements.', 'warning')
        else:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            user = {"username": username, "password": hashed_password, "cart": [], "purchased_products": []}
            try:
                mongo.db.users.insert_one(user)
                flash('Registration successful! You can now log in.', 'success')
                return redirect(url_for('login'))
            except:
                flash('Username already exists.', 'danger')

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form.get('password')

        update_data = {'name': name, 'email': email}
        if password:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            update_data['password'] = hashed_password.decode('utf-8')

        mongo.db.users.update_one({'_id': ObjectId(session['user_id'])}, {'$set': update_data})
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        product_name = request.form['product_name']
        price = float(request.form['price'])
        description = request.form['description']
        tags = request.form['tags'].split(',')

        mongo.db.products.insert_one({
            "product_name": product_name,
            "price": price,
            "description": description,
            "tags": tags,
            "created_at": pd.Timestamp.now()
        })

        flash('Product added successfully!', 'success')
        return redirect(url_for('add_product'))

    return render_template('add_product.html')

if __name__ == '__main__':
    app.run(debug=True)
