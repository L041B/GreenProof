from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from app.controllers import company_controller, user_controller, notifications_controller, eth_account_controller
from app.routes.auth_routes import get_user_info
import os
import geonamescache
import uuid
import re

bp = Blueprint('company', __name__)
gc = geonamescache.GeonamesCache()

# Helper functions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_size(file):
    MAX_FILE_SIZE = 3 * 1024 * 1024  # 3MB in bytes
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size <= MAX_FILE_SIZE

# Validate email, phone, and website
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Validate phone number
def validate_phone(phone):
    pattern = r'^\+?\d{10,15}$'
    return re.match(pattern, phone) is not None

# Validate website
def validate_website(website):
    http = website.startswith('http://')
    if not website:
        return True
    if not http:
        website = 'https://' + website
    return http 

# Validate website URL
@bp.route('/company_register', methods=['GET', 'POST'])
def company_register():
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    if not user_id:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            if 'id' not in session:
                return jsonify({'success': False, 'error': 'User not authenticated'})

            # Get user email for notification
            user = user_controller.get_user_by_id(session['id'])
            if not user:
                return jsonify({'success': False, 'error': 'User not found'})
            
            company_id = uuid.uuid4().int & (1<<32)-1
            company_phone_number = request.form.get('phone')

            company_phone_pattern = re.compile(r'^\+?\d{10,15}$')
            if not company_phone_pattern.match(company_phone_number):
                return jsonify({'success': False, 'error': 'Invalid phone number format'})


            # Extract form data
            company_data = {
                'company_id': company_id,
                'company_name': request.form['companyName'],
                'company_phone_number': request.form['phone'],
                'company_email': request.form['email'],
                'company_industry': request.form['industry'],
                'company_country': request.form['country'],
                'company_city': request.form['city'],
                'company_address': request.form['address'],
                'company_description': request.form['description'],
                'company_website': request.form.get('website'),
                'company_image': request.files.get('logo') if 'logo' in request.files else None,
                'sender_email': user['email']  # Add sender email
            }

            # Validate company name
            if company_controller.check_company_exists(company_data['company_name']):
                return jsonify({
                    'success': False,
                    'error': 'A company with this name already exists'
                })
            
           
            # Create company
            result = company_controller.create_company(**company_data)

            if result['success']:
                # Get user info for notification
                user = user_controller.get_user_by_id(user_id)
                if user:
                    success = company_controller.send_admin_notification(user, company_data)
                    if not success:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to send notification to admin'
                        })
                    notifications_controller.send_notification_to_admin('company registration', user['email'], company_id)
                return jsonify({
                    'success': True,
                    'redirect': url_for('main.home')
                })
                
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to create company')
            })

        except Exception as e:
            print(f"Error in company registration: {e}")
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred'
            })

    return render_template('company_register.html', user_id=user_id, user=user, is_admin=is_admin, is_company_admin=is_company_admin, notifications = notifications)

# Route for searching companies
@bp.route('/search_companies', methods=['GET'])
def search_companies():
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    search_query = request.args.get('query', '').strip()
    
    try:
        if search_query != "":
            companies = company_controller.search_companies(search_query)
        else:
            companies = company_controller.get_all_companies_sorted()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'companies': companies})
        
        return render_template('search_companies.html', 
                             companies=companies, 
                             user_id=user_id, 
                             user=user, 
                             is_admin=is_admin, 
                             is_company_admin=is_company_admin,
                             search_query=search_query,
                             notifications = notifications,)
    except Exception as e:
        print(f"Error in search: {e}")
        return render_template('search_companies.html', 
                             companies=[], 
                             user_id=user_id, 
                             user=user, 
                             is_admin=is_admin, 
                             is_company_admin=is_company_admin,
                             notifications = notifications)

# Route for company information
@bp.route('/information_company/<int:company_id>')
def information_company(company_id):
    user_id, user, is_admin, is_company_admin, notifications= get_user_info()
    
    company = company_controller.get_company_by_id(company_id)
    if company is None:
        return "Company not found.", 404

    info_of_admin = company_controller.get_admin_info_by_company(company_id)
        
    if not company['status'] and not is_admin:
        return "Unauthorized", 403

    # Get token balance if ETH address exists
    token_balance = 0
    if company.get('eth_address'):
        if company['eth_address'] == None:
            token_balance=0
        else:
            token_balance = eth_account_controller.get_token_balance(company['eth_address'])
        
    return render_template('information_company.html', 
                         company=company,
                         token_balance=token_balance,
                         user_id=user_id,
                         user=user,
                         is_admin=is_admin,
                         info_of_admin=info_of_admin,
                         is_company_admin=is_company_admin,
                         notifications = notifications)

# Route for getting countries
@bp.route('/get_countries', methods=['GET'])
def get_countries():
    query = request.args.get('query', '')
    
    countries = gc.get_countries()
    
    filtered_countries = [
        {"id": country_code, "text": country_info['name']}
        for country_code, country_info in countries.items()
        if query.lower() in country_info['name'].lower()
    ]
    
    return jsonify(filtered_countries)

# Route for getting cities
@bp.route('/get_cities', methods=['GET'])
def get_cities():
    country_code = request.args.get('country_code')
    if not country_code:
        return jsonify({'error': 'Country code is required'}), 400

    cities = gc.get_cities()

    if isinstance(cities, dict):
        cities_in_country = []
        for city_key, city in cities.items():
            if city['countrycode'] == country_code:
                cities_in_country.append(city['name'])
    else:
        return jsonify({'error': 'Data format is incorrect'}), 500

    return jsonify(cities_in_country)

# Route for getting companies of administrator
@bp.route('/companies_of_administrator', methods=['GET'])
def companies_administrator():
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    
    try:
        company_ids = company_controller.get_companyID_by_owner(user_id)

        companies = []
        for company_id in company_ids:
            company = company_controller.get_company_by_id(company_id['company_id'])
            if company:
                companies.append(company)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'companies': companies})
        
        return render_template('manage_companies.html', 
                             companies=companies, 
                             user_id=user_id, 
                             user=user, 
                             is_admin=is_admin, 
                             is_company_admin=is_company_admin,
                             notifications=notifications)
    except Exception as e:
        print(f"Errore durante la ricerca delle compagnie: {e}")
        return render_template('manage_companies.html', 
                             companies=[], 
                             user_id=user_id, 
                             user=user, 
                             is_admin=is_admin, 
                             notifications=notifications,
                             is_company_admin=is_company_admin)

# Route for modifying company
@bp.route('/modify_company/<int:company_id>', methods=['GET', 'POST'])
def modify_company(company_id):
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    
    company = company_controller.get_company_by_id(company_id)
    if company is None:
        return jsonify({"success": False, "error": "Company not found"}), 404

    if not company['status'] and not is_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    if request.method == 'POST':
        try:
            # Get existing company data
            existing_company = company_controller.get_company_by_id(company_id)
            
            # Merge form data with existing data (keep existing values if not in form)
            company_data = {
                'company_name': request.form.get('company_name', existing_company['company_name']),
                'company_phone_number': request.form.get('company_phone_number', existing_company['company_phone_number']),
                'company_email': request.form.get('company_email', existing_company['company_email']),
                'company_industry': request.form.get('company_industry', existing_company['company_industry']),
                'company_website': request.form.get('company_website', existing_company['company_website']),
                'company_description': request.form.get('company_description', existing_company['company_description'])
            }

            # Only validate fields that are actually being updated
            if company_data['company_name'] != existing_company['company_name']:
                if len(company_data['company_name']) < 2:
                    return jsonify({"success": False, "error": "Company name must be at least 2 characters long"})

            if company_data['company_email'] != existing_company['company_email']:
                if not validate_email(company_data['company_email']):
                    return jsonify({"success": False, "error": "Please enter a valid email address"})

            if company_data['company_phone_number'] != existing_company['company_phone_number']:
                if not validate_phone(company_data['company_phone_number']):
                    return jsonify({"success": False, "error": "Please enter a valid phone number (+XX followed by 10-15 digits)"})

            if company_data['company_website'] != existing_company['company_website']:
                if company_data['company_website'] and not validate_website(company_data['company_website']):
                    return jsonify({"success": False, "error": "Website URL must start with https://"})

            if company_data['company_description'] != existing_company['company_description']:
                if len(company_data['company_description']) > 1500:
                    return jsonify({"success": False, "error": "Description must not exceed 1500 characters"})

            # Handle image upload separately
            if 'company_logo' in request.files and request.files['company_logo'].filename:
                file = request.files['company_logo']
                if not allowed_file(file.filename):
                    return jsonify({"success": False, "error": "Invalid file type"})
                if not validate_file_size(file):
                    return jsonify({"success": False, "error": "File size must not exceed 3MB"})
                try:
                    company_image_url = company_controller.upload_company_image(company_id, file)
                    if company_image_url:
                        company_data['company_image'] = company_image_url
                    else:
                        return jsonify({"success": False, "error": "Failed to upload image"})
                except Exception as e:
                    print(f"Error uploading image: {e}")
                    return jsonify({"success": False, "error": "Failed to upload image"})
            else:
                # Keep existing image
                company_data['company_image'] = existing_company.get('company_image')

            # Update company with merged data
            result = company_controller.update_company(company_id, **company_data)
            if result.get('success'):
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": result.get('message', "Failed to update company")})

        except Exception as e:
            print(f"Error in modify_company: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    return render_template('modify_company.html', 
                         company=company,
                         user_id=user_id,
                         user=user,
                         is_admin=is_admin,
                         is_company_admin=is_company_admin,
                         notifications=notifications)

# Route for deleting company
@bp.route('/delete_company/<int:company_id>', methods=['POST'])
def delete_company(company_id):
    _, user, _, is_company_admin, _ = get_user_info()
    if not is_company_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    success = company_controller.delete_company_notification(user["email"],company_id)
    return jsonify({'success': success, 'error': None if success else 'Failed to delete company'})

# Route for managing products
@bp.route('/manage_product/<int:company_id>', methods=['GET', 'POST'])
def manage_product(company_id):
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    products = company_controller.get_product_by_company_id(company_id)
    type_of_company = company_controller.type_of_company_by_id(company_id)
    comp_indu=type_of_company.data
    type_of_company = comp_indu[0]['company_industry']

    if request.method == 'POST':
        try:

            product_id = int(request.form['product_id'])
            updated_data = {
                'name': request.form['product_name'],
                'description': request.form['product_description'],
                'quantity': int(request.form['product_quantity'])
            }

            response = company_controller.update_product_in_products_table(product_id, updated_data)

            if isinstance(response, dict) and 'error' in response:
                return jsonify({'error': response['error']}), 500

            return redirect(url_for('company.manage_product', company_id=company_id))


        except Exception as e:
            print(f"Error updating product: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500  # Return error message

    return render_template('manage_product.html', 
                           user_id=user_id,
                           company_id=company_id, 
                           products=products,
                           type_of_company=type_of_company,
                           user=user, 
                           is_admin=is_admin, 
                           is_company_admin=is_company_admin,
                           notifications=notifications)

# Route for adding product
@bp.route('/add_product', methods=['POST'])
def add_product():
    data = request.get_json()

    product_name = data.get('name')
    product_description = data.get('description')
    product_quantity = data.get('quantity')
    company_id = data.get('company_id')
    type_of_company=data.get('type_of_company')   
    type_of_company=type_of_company.lower()
   
    response=False

    if not product_name or not company_id:
        return jsonify({'error': 'Product name, quantity, and company ID are required'}), 400

    if type_of_company =="manufacturer":
        if not product_quantity:
            return jsonify({'error': 'Product name, quantity, and company ID are required'}), 400

        response = company_controller.new_product_by_farmer(company_id=company_id,
                                        product_name=product_name,
                                        product_description=product_description,
                                        product_quantity=product_quantity)
    elif type_of_company == "processor":
        response = company_controller.new_product_by_processor(company_id=company_id,
                                        product_name=product_name,
                                        product_description=product_description,
                                        product_quantity=product_quantity)

    if response:
        return jsonify({'success': True, 'message': 'Product added successfully'}), 200
    else:   
        return jsonify({'error': False, 'message':'Product already exist'}), 500
    
    
    
# Route for deleting product
@bp.route('/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        response = company_controller.delete_product(product_id)

        if response:
            return jsonify({'success': True, 'message': 'Product deleted successfully'}), 200
        else:
            return jsonify({'error': 'Failed to delete product'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500
     
# Route for deleting product by seller
@bp.route('/delete_product_by_seller/<int:product_id>', methods=['DELETE'])
def delete_product_by_seller(product_id):
    try:
        response = company_controller.delete_product_of_seller(product_id)

        if response:
            return jsonify({'success': True, 'message': 'Product deleted successfully'}), 200
        else:
            return jsonify({'error': 'Failed to delete product'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500  

# Route for managing product by processor
@bp.route('/manage_product_by_processor/<int:company_id>', methods=['GET', 'POST'])
def manage_product_by_processor(company_id):
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    products_duplicate = company_controller.get_products_by_company_id(company_id)
    products = []
    seen_names = set()

    for product in products_duplicate:
        name = product["name"].lower()
        if name not in seen_names:
            products.append(product)
            seen_names.add(name)

    type_of_company = company_controller.type_of_company_by_id(company_id)
    comp_indu=type_of_company.data
    type_of_company = comp_indu[0]['company_industry']
    
    if request.method == 'POST':
        try:
            product_id = int(request.form['product_id'])
            updated_data = {
                'name': request.form['product_name'],
                'description': request.form['product_description'],
                'quantity': int(request.form['product_quantity'])
            }

            response = company_controller.update_product_in_products_table(product_id, updated_data)

            if isinstance(response, dict) and 'error' in response:
                return jsonify({'error': response['error']}), 500
            
            return redirect(url_for('company.manage_product_by_processor', company_id=company_id))


        except Exception as e:
            print(f"Error updating product: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500  # Return error message

    return render_template('processor_manage_product.html', 
                           user_id=user_id,
                           company_id=company_id, 
                           products=products,
                           type_of_company=type_of_company,
                           user=user, 
                           is_admin=is_admin, 
                           is_company_admin=is_company_admin,
                           notifications=notifications)

# Route for creating product request
@bp.route('/request_creation_product/<product>/<int:company_id_buyer>/', methods=['GET'])
def request_creation_product(product, company_id_buyer):
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    
    companies = company_controller.get_companies_by_industry("manufacturer")
    carriers = company_controller.get_companies_by_industry("transporter")

    manufacturers = []
    transporters = []
    products_by_manufacturer = {}

    for company in companies:
        company_id = company['company_id']
        if company['eth_address']:
            manufacturers.append({'id': company_id, 'name': company['company_name']})
        
            products = company_controller.get_product_by_company_id(company_id)
            products_by_manufacturer[company_id] = products

    for carrier in carriers:
        if carrier['eth_address']:
            transporters.append({'id': carrier['company_id'], 'name': carrier['company_name']})


    return render_template(
        'request_creation_product.html',
        user_id=user_id,
        user=user,
        is_admin=is_admin,
        product=product,
        company_id= company_id_buyer,
        manufacturers=manufacturers,
        transporters=transporters,
        products_by_manufacturer=products_by_manufacturer,
        is_company_admin=is_company_admin,
        notifications=notifications
    )

# Route for creating product request
@bp.route('/create_product_request', methods=['POST'])
def create_product_request():
    data = request.get_json()
   
    company_id = data.get('id_buyer')
    id_supplier = data.get('manufacturer')
    id_product = data.get('id_product')
    id_raw_material = data.get('id_raw_material')
    quantity = data.get('quantity')
    quantity_of_raw_material = data.get('manufacturerQuantity')
    id_transporter = data.get('carrier')
    transport_date = data.get('transportDate')
    distance_to_travel = data.get('distance')

    if not company_id:
        return jsonify({"error": "Company ID is required"}), 400

    result = company_controller.create_product_request(
        company_id,
        id_supplier,
        id_product,
        id_raw_material,
        quantity,
        quantity_of_raw_material,
        id_transporter,
        transport_date,
        distance_to_travel,
    )

    buyer_admins = company_controller.get_owners_by_company(company_id)
    supplier_admins = company_controller.get_owners_by_company(id_supplier)
    transporter_admins = company_controller.get_owners_by_company(id_transporter)

   
    sender_email = buyer_admins[0]['email'] if buyer_admins else None

    if sender_email:
        for admin in supplier_admins:
            notifications_controller.create_notification_with_product(
                type="order_request",
                sender=sender_email,
                receiver=admin['email'],
                product=result.data[0]['id'],
                company_id=id_supplier
            )

        for admin in transporter_admins:
            notifications_controller.create_notification_with_product(
                type="transport_request",
                sender=sender_email,
                receiver=admin['email'],
                product=result.data[0]['id'],
                company_id=id_transporter
            )
    else:
        print("No Amministrator found for the buyer company.")


    if result:
        return jsonify({
            "success": True,  # Include success here
            "status": "success",
            "data": result.data
        }), 200
    else:
        return jsonify({
            "status": "error"
        }), 400

# Route for managing product by seller
@bp.route('/manage_product_by_seller/<int:company_id>', methods=['GET', 'POST'])
def manage_product_by_seller(company_id):
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    products_of_seller = company_controller.get_products_by_seller(company_id)
    merged_products = []
    
    for product in products_of_seller.data:
        product_details = company_controller.get_information_by_id_product(product['id_product'])
        
        matched_product = None
        for item in product_details.data:
            if item['id'] == product['id_product']:
                matched_product = item
                break
        
        if matched_product:
            merged_product = {
                'id_product': product['id_product'],
                'name': matched_product['name'],
                'description': matched_product['description'],
                'quantity': product['quantity']
            }
            merged_products.append(merged_product)
    
    type_of_company = company_controller.type_of_company_by_id(company_id)
    comp_indu = type_of_company.data
    type_of_company = comp_indu[0]['company_industry']

    if request.method == 'POST':
        try:
            
            product_id = request.form.get('product_id')
            quantity = request.form.get('product_quantity')
            
            # Validate the inputs
            if not product_id.isdigit() or not quantity.isdigit():
                return jsonify({'success': False, 'error': 'Invalid product ID or quantity.'}), 400

            product_id = int(product_id)
            quantity = int(quantity)
            

            # Call the function to update the product in the database
            response = company_controller.update_quantity_of_seller(product_id, quantity)

            if isinstance(response, dict) and 'error' in response:
                return jsonify({'success': False, 'error': response['error']}), 500

            return redirect(url_for('company.manage_product_by_seller', company_id=company_id))

        except Exception as e:
            print(f"Error updating product: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500  # Return error message

    # If the request is GET, render the template with the products
    return render_template('seller_manage_product.html', 
                           user_id=user_id,
                           company_id=company_id, 
                           products=merged_products,
                           type_of_company=type_of_company,
                           user=user, 
                           is_admin=is_admin, 
                           is_company_admin=is_company_admin,
                           notifications=notifications)

# Route for managing product by transporter
@bp.route('/manage_product_by_transporter/<int:company_id>', methods=['GET', 'POST'])
def manage_product_by_transporter(company_id):
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    type_of_company = company_controller.type_of_company_by_id(company_id)
    today = datetime.today().date()

    transports_list = []

    transports = company_controller.get_information_of_transporter(company_id)

    for transport in transports.data:
        transport_dict = {
            'id': transport['id'],
            'date_delivery': transport['date_delivery'],
            'distance': transport['distance'],
            'id_buyer': transport['id_buyer'],
            'id_seller': transport['id_seller'],
            'created_at': transport['created_at'],
            'id_transporter': transport['id_transporter']
        }

        buyer_response = company_controller.get_company_by_id(transport['id_buyer'])
        buyer = buyer_response['company_name']
        transport_dict['buyer'] = buyer

        seller_response = company_controller.get_company_by_id(transport['id_seller'])
        seller = seller_response['company_name']
        
        transport_dict['seller'] = seller

        transport_date = datetime.strptime(transport['date_delivery'], "%Y-%m-%d").date()

        # Check if the transport is delivered
        transport_dict['delivered'] = transport_date <= today  # True if delivery date is before or on today, else False

        transports_list.append(transport_dict)

    
    comp_indu=type_of_company.data
    type_of_company = comp_indu[0]['company_industry']

    return render_template('transporter_manage_product.html', 
                           user_id=user_id,
                           company_id=company_id, 
                           transports_list= transports_list,
                           type_of_company=type_of_company,
                           today=today,
                           user=user, 
                           is_admin=is_admin, 
                           is_company_admin=is_company_admin,
                           notifications=notifications)

# Route for seller request
@bp.route('/seller_request/<int:company_id_buyer>', methods=['GET'])
def seller_request(company_id_buyer):
    # Retrieve user and company details
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    # Fetch companies based on industry type
    manufacturers = company_controller.get_companies_by_industry("manufacturer")
    processors = company_controller.get_companies_by_industry("processor")
    transporters = company_controller.get_companies_by_industry("transporter")

    # Initialize dictionaries to hold products by manufacturer and lists for transporters, manufacturers, and processors
    products_by_manufacturer = {}
    products_by_processors = {}
    manufacturer_list = []
    transporter_list = []
    processor_list = []  # Added list for processors

    # Loop through manufacturers to collect data
    for company in manufacturers:
        company_id = company['company_id']
        if company['eth_address']:
            manufacturer_list.append({'id': company_id, 'name': company['company_name']})
        
            # Get products associated with each manufacturer
            products_by_manufacturer[company_id] = company_controller.get_product_by_company_id(company_id)

    # Loop through transporters to collect transporter data
    for carrier in transporters:
        if carrier['eth_address']:
            transporter_list.append({'id': carrier['company_id'], 'name': carrier['company_name']})
    
    # Loop through processors to collect processor data
    for processor in processors:
        company_id_processor = processor['company_id']
        if processor['eth_address']:
            processor_list.append({'id': company_id_processor, 'name': processor['company_name']})
            products_by_processors[company_id_processor] = company_controller.get_product_by_company_id(company_id_processor)
  
    # Render template with necessary data
    return render_template(
        'seller_request.html',
        user_id=user_id,
        user=user,
        is_admin=is_admin,
        company_id=company_id_buyer,
        manufacturers=manufacturer_list,  # Send manufacturers list
        transporters=transporter_list,   # Send transporters list
        processors=processor_list,  # Send processors list (added this)
        products_by_manufacturer=products_by_manufacturer,  # Send product data for each manufacturer
        products_by_processor= products_by_processors,
        is_company_admin=is_company_admin,
        notifications=notifications
    )


# Route for selecting company to manage product
@bp.route('/select_company_to_manage_product', methods=['GET', 'POST'])
def select_company_to_manage_product():
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    
    company_ids = company_controller.get_companyID_by_owner(user_id)
    companies = []
    for cid in company_ids:
        comp = company_controller.get_company_by_id(cid['company_id'])
        if comp['eth_address'] != None:
            companies.append(comp)

    if request.method == 'POST':
        selected_company_id = request.form.get('company_id')

        comp = company_controller.get_company_by_id(selected_company_id)
        if (comp['company_industry'] == "seller"):
            return redirect(url_for('company.manage_product_by_seller', company_id=selected_company_id))
        elif (comp['company_industry'] == "processor"):
            return redirect(url_for('company.manage_product_by_processor', company_id=selected_company_id))
        elif (comp['company_industry'] == "manufacturer"):
            return redirect(url_for('company.manage_product', company_id=selected_company_id))
        elif (comp['company_industry'] == "transporter"):
            return redirect(url_for('company.manage_product_by_transporter', company_id=selected_company_id))
    
    return render_template('select_company_to_manage_product.html',
                           companies=companies,
                           user_id=user_id,
                           user=user,
                           is_admin=is_admin,
                           is_company_admin=is_company_admin,
                           notifications=notifications)

# Route for checking ETH address
@bp.route('/check_eth_address', methods=['GET'])
def check_eth_address():
    eth_address = request.args.get('address')
    company_id = request.args.get('company_id')
    
    if not eth_address:
        return jsonify({'available': False, 'error': 'No address provided'})
        
    # Validate format
    if not re.match(r'^0x[a-fA-F0-9]{40}$', eth_address):
        return jsonify({'available': False, 'error': 'Invalid address format'})
        
    # Check uniqueness
    is_unique = company_controller.check_eth_address_unique(eth_address, company_id)
    return jsonify({'available': is_unique})

# Route for managing tokens
@bp.route('/manage_tokens', methods=['GET', 'POST'])
def manage_tokens():
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    
    company_ids = company_controller.get_companyID_by_owner(user_id)
    companies = []
    for cid in company_ids:
        comp = company_controller.get_company_by_id(cid['company_id'])
        if comp['eth_address'] != 'no address' and comp['eth_address'] != None:
            companies.append(comp)

    if len(companies) == 1:
        return redirect(url_for('company.manage_tokens_detail', company_id=companies[0]['company_id']))
    
    if request.method == 'POST':
        selected_company_id = request.form.get('company_id')
        return redirect(url_for('company.manage_tokens_detail', company_id=selected_company_id))
    
    return render_template('select_company_to_manage_tokens.html',
                           companies=companies,
                           user_id=user_id,
                           user=user,
                           is_admin=is_admin,
                           is_company_admin=is_company_admin,
                           notifications=notifications)

# Route for managing tokens details
@bp.route('/manage_tokens_details/<int:company_id>', methods=['GET', 'POST'])
def manage_tokens_detail(company_id):
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    
    company = company_controller.get_company_by_id(company_id)
    if company is None:
        return "Company not found", 404

    if not company['status'] and not is_admin:
        return "Unauthorized", 403

    current_page = request.args.get("page", default=1, type=int)
    token_balance = 0
    transactions = []
    total_pages = 1  # Default value
    
    if company.get('eth_address'):
        token_balance = eth_account_controller.get_token_balance(company['eth_address'])
        # Use get_paginated_transactions instead of get_transactions_for_company
        transactions, total_pages = eth_account_controller.get_paginated_transactions(
            company['eth_address'], 
            page=current_page
        )

    # Create a sliding window of page numbers (show max 4 pages)
    if total_pages <= 4:
        page_numbers = list(range(1, total_pages + 1))
    else:
        if current_page <= 2:
            page_numbers = list(range(1, 5))
        elif current_page >= total_pages - 1:
            page_numbers = list(range(total_pages - 3, total_pages + 1))
        else:
            page_numbers = list(range(current_page - 1, current_page + 3))

    return render_template('manage_token.html', 
                         company=company,
                         token_balance=token_balance,
                         transactions=transactions,
                         user_id=user_id,
                         user=user,
                         is_admin=is_admin,
                         is_company_admin=is_company_admin,
                         notifications=notifications,
                         current_page=current_page,
                         total_pages=total_pages,
                         page_numbers=page_numbers)

# Route for checking available companies
@bp.route('/check_available_companies/<int:company_id>')
def check_available_companies(company_id):
    amount = request.args.get('amount', type=float)
    if not amount:
        return jsonify({'error': 'Amount is required'}), 400
        
    companies = eth_account_controller.find_companies_with_sufficient_tokens(amount)
    companies = [c for c in companies if c['company_id'] != company_id]
    
    return jsonify({'companies': companies})

# Route for submitting token request
@bp.route('/submit_token_request', methods=['POST'])
def submit_token_request():
    user_id, _, _, is_company_admin, _ = get_user_info()
    if not user_id or not is_company_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'})

    data = request.get_json()
    amount = data.get('amount')
    receiver_address = data.get('receiver_address')
    sender_company_id = data.get('company_id')
    sender_id = data.get('user_id')

    try:
        # Get receiver company details
        receiver_company = company_controller.get_company_by_eth_address(receiver_address)
        if not receiver_company:
            return jsonify({'success': False, 'error': 'Receiver company not found'})

        # Get sender company details for notification
        sender_company = company_controller.get_company_by_id(sender_company_id)
        if not sender_company:
            return jsonify({'success': False, 'error': 'Sender company not found'})
        
        sender_email = user_controller.get_user_by_id(sender_id)['email']
        same_request = uuid.uuid4().int & (1<<32)-1

        # Create notification for receiver company admins
        success = company_controller.create_token_request_notification(
            sender_email = sender_email,
            sender_company_id=sender_company_id,
            receiver_company_id=receiver_company['company_id'],
            amount=amount,
            same_request=same_request
        )

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to create token request'})

    except Exception as e:
        print(f"Error submitting token request: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Route for approving token request
@bp.route('/approve_token_request/<notification_id>', methods=['POST'])
def approve_token_request(notification_id):
    user_id, _, _, is_company_admin, _ = get_user_info()
    if not user_id or not is_company_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        # Get notification details
        notification = notifications_controller.get_notification_by_id(notification_id)
        if not notification:
            return jsonify({'success': False, 'error': 'Notification not found'})

        # Get sender and receiver company details
        

        sender_company = company_controller.get_company_by_id(notification['sender_company_id'])
        receiver_company = company_controller.get_company_by_id(notification['company_id'])
        
        if not sender_company or not receiver_company:
            return jsonify({'success': False, 'error': 'Company information not found'})

        # Verify sender's ETH address exists
        if not sender_company.get('eth_address'):
            return jsonify({'success': False, 'error': 'Sender company has no ETH address'})

        # Verify receiver's ETH address exists and matches connected MetaMask account
        if not receiver_company.get('eth_address'):
            return jsonify({'success': False, 'error': 'Your company has no ETH address'})

        # Prepare transaction data
        transfer_data = eth_account_controller.initiate_token_transfer(
            receiver_company['eth_address'],
            sender_company['eth_address'],
            notification['requested_token']
        )
        
        if not transfer_data['success']:
            return jsonify({'success': False, 'error': transfer_data.get('error', 'Failed to prepare transaction')})
        
        approve_notification = notifications_controller.send_token_notification_to_all_company_admin('token request approved', notification_id)
        if not approve_notification:
            return jsonify({'success': False, 'error': 'Failed to send notification'})

        # Return transaction data for MetaMask to sign
        return jsonify({
            'success': True,
            'transaction': transfer_data['tx_data'],
            'notification_id': notification_id
        })

    except Exception as e:
        print(f"Error in approve_token_request: {e}")
        return jsonify({'success': False, 'error': str(e)})
    
# Route for rejecting token request
@bp.route('/reject_token_request/<notification_id>', methods=['POST'])
def reject_token_request(notification_id):
    user_id, _, _, is_company_admin, _ = get_user_info()
    if not user_id or not is_company_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        # Delete notification
        reject_notification = notifications_controller.send_token_notification_to_all_company_admin('token request rejected', notification_id)
        
        success = notifications_controller.delete_notification_for_all_admin_company(notification_id)
        
        if success and reject_notification:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to reject token request'})

    except Exception as e:
        print(f"Error rejecting token request: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Route for completing token transfer
@bp.route('/complete_token_transfer/<notification_id>', methods=['POST'])
def complete_token_transfer(notification_id):
    user_id, _, _, is_company_admin, _ = get_user_info()
    if not user_id or not is_company_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()
        tx_hash = data.get('transactionHash')
        
        if not tx_hash:
            return jsonify({'success': False, 'error': 'No transaction hash provided'}) 

        # Delete notification for all admins
        success = notifications_controller.delete_notification_for_all_admin_company(notification_id)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to update notification status'})

    except Exception as e:
        print(f"Error completing token transfer: {e}")
        return jsonify({'success': False, 'error': str(e)})