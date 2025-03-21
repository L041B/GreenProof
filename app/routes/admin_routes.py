from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from app.routes.auth_routes import get_user_info
from app.controllers import company_controller, user_controller
from app.controllers import notifications_controller

bp = Blueprint('admin', __name__)

# Route for admin approve company
@bp.route('/company/approve/<int:company_id>', methods=['POST'])
def approve_company(company_id):
    _, _, is_admin, _, _ = get_user_info()
    if not is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'})
    
    success = company_controller.approve_company(company_id)
    return jsonify({'success': success, 'error': None if success else 'Failed to approve company'})

# Route for admin reject company
@bp.route('/company/reject/<int:company_id>', methods=['POST'])
def reject_company(company_id):
    _, _, is_admin, _, _ = get_user_info()
    if not is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'})
    
    success = company_controller.reject_company(company_id)
    return jsonify({'success': success, 'error': None if success else 'Failed to reject company'})

# Route for admin eliminate company
@bp.route('/company/eliminate/<int:company_id>', methods=['POST'])
def eliminate_company(company_id):
    _, _, is_admin, _, _ = get_user_info()
    if not is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'})
    
    success = company_controller.eliminate_company(company_id)
    return jsonify({'success': success, 'error': None if success else 'Failed to eliminate company'})

# Route for admin approve user
@bp.route('/notification/<notification_id>/<action>', methods=['POST'])
def process_notification(notification_id,action):
    _, _, is_admin, _, _ = get_user_info()
    if not is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'})
        
    try:
        # Get notification details
        notif = notifications_controller.get_notification_by_id(notification_id)
        if not notif:
            return jsonify({'success': False, 'error': 'Notification not found'})
        company_id = notif['company_id']
        sender_email = notif['receiver_email']
        receiver_email = notif['sender_email']
        
        # Process based on notification type
        success = False

        if action == 'approve registration':
            success = company_controller.approve_company(sender_email, receiver_email, company_id)
        elif action == 'reject registration':
            success = company_controller.reject_company(sender_email, receiver_email, company_id)
        elif action == 'approve elimination':
            success = company_controller.eliminate_company(sender_email, receiver_email, company_id)
        elif action == 'reject elimination':
            success = notifications_controller.create_notification("rejection elimination company", sender_email, receiver_email, company_id)
            
        # If company operation was successful, delete the notification
        if success:
            notifications_controller.delete_notification(notification_id)
            return jsonify({'success': True})
            
        return jsonify({'success': False, 'error': 'Failed to process request'})
        
    except Exception as e:
        print(f"Error processing notification: {e}")
        return jsonify({'success': False, 'error': 'An error occurred'})

# Route for admin manage company   
@bp.route('/admin_manage_company', methods=['GET'])
def admin_manage_company():
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    search_query = request.args.get('query', '').strip()

    try:
        companies = []
        if search_query != "":
            companies = company_controller.search_companies(search_query)
        else:
            companies = company_controller.get_all_companies_sorted()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'companies': companies})
        
        return render_template('manage_companies.html', 
                             companies=companies, 
                             user_id=user_id, 
                             user=user, 
                             is_admin=is_admin, 
                             is_company_admin=is_company_admin,
                             notifications=notifications,
                             search_query=search_query)
    except Exception as e:
        print(f"Errore durante la ricerca delle compagnie: {e}")
        return render_template('manage_companies.html', 
                             companies=[], 
                             user_id=user_id, 
                             user=user, 
                             is_admin=is_admin,
                             notifications=notifications,
                             search_query=search_query, 
                             is_company_admin=is_company_admin)
    
# Route for admin manage user
@bp.route('/admin_manage_user', methods=['GET', 'POST'])
def admin_manage_user():
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    user_id, user, is_admin, is_company_admin, notifications = get_user_info()
    unique_admin=user_controller.get_unique_company_admins()

    if not user_id:
        return redirect(url_for('login'))
    
    search_query = request.args.get('search', '')

    if search_query:
        users_info = [user for user in user_controller.get_users_by_name_or_surname(search_query) if user["id"] != user_id]
    else:
        users_info = [user for user in user_controller.get_all_users() if user["id"] != user_id]


    return render_template('manage_user.html', 
                           user_id=user_id, 
                           user=user, 
                           is_admin=is_admin, 
                           is_company_admin=is_company_admin, 
                           users_info=users_info,
                           search_query=search_query,
                           unique_admins=unique_admin,
                           notifications=notifications)

# Route for admin delete user
@bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    try:
        response = user_controller.delete_user(user_id)
        if response:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete user'}), 500

    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({'success': False, 'error': 'An error occurred'}), 500
