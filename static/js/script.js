// Cart functionality
document.addEventListener('DOMContentLoaded', function() {
    // Initialize cart counter
    updateCartCount();

    // Add to cart functionality
    const addToCartButtons = document.querySelectorAll('.add-to-cart');
    addToCartButtons.forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            const productId = this.dataset.productId;
            
            try {
                const response = await fetch('/cart', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ product_id: productId })
                });

                if (response.ok) {
                    showNotification('Product added to cart!', 'success');
                    updateCartCount();
                    animateCartIcon();
                } else {
                    showNotification('Failed to add product to cart', 'error');
                }
            } catch (error) {
                showNotification('An error occurred', 'error');
            }
        });
    });

    // Notification system
    function showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type} fade-in`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    // Cart counter update
    function updateCartCount() {
        const cartCount = document.querySelector('.cart-count');
        if (cartCount) {
            fetch('/cart')
                .then(response => response.json())
                .then(data => {
                    cartCount.textContent = data.count;
                });
        }
    }

    // Cart icon animation
    function animateCartIcon() {
        const cartIcon = document.querySelector('.cart-badge');
        cartIcon.classList.add('bounce');
        setTimeout(() => {
            cartIcon.classList.remove('bounce');
        }, 1000);
    }

    // Product image lazy loading
    const images = document.querySelectorAll('img[data-src]');
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
                observer.unobserve(img);
            }
        });
    });

    images.forEach(img => imageObserver.observe(img));

    // Smooth scroll
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    showFieldError(field, 'This field is required');
                } else {
                    removeFieldError(field);
                }
            });

            if (!isValid) {
                e.preventDefault();
            }
        });
    });

    function showFieldError(field, message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        errorDiv.textContent = message;
        
        if (!field.nextElementSibling?.classList.contains('field-error')) {
            field.parentNode.insertBefore(errorDiv, field.nextElementSibling);
        }
        
        field.classList.add('error');
    }

    function removeFieldError(field) {
        const errorDiv = field.nextElementSibling;
        if (errorDiv?.classList.contains('field-error')) {
            errorDiv.remove();
        }
        field.classList.remove('error');
    }

    // Product filtering and sorting
    const sortSelect = document.querySelector('.sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            const products = Array.from(document.querySelectorAll('.product-card'));
            const sortBy = this.value;
            
            products.sort((a, b) => {
                const aValue = a.dataset[sortBy];
                const bValue = b.dataset[sortBy];
                
                if (sortBy === 'price') {
                    return parseFloat(aValue) - parseFloat(bValue);
                }
                return aValue.localeCompare(bValue);
            });
            
            const container = document.querySelector('.product-grid');
            products.forEach(product => container.appendChild(product));
        });
    }

    // Mobile menu toggle
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    
    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', () => {
            navLinks.classList.toggle('show');
            menuToggle.classList.toggle('active');
        });
    }
});