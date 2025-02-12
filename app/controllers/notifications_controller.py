from app import supabase
import uuid

def create_notification(type, sender, receiver, company_id = None):

    try:

        supabase.table('notifications').insert({
        'id_notifications': str(uuid.uuid4()),
        'type': type,
        'sender_email': sender,
        'receiver_email': receiver,
        'status': 'unread',
        'company_id': company_id
        })
        return True
    
    except Exception as e:
        print(f"Error creating notification: {e}")
        return False
    

def get_notifications_by_email(email):
    try:
        response = supabase.table('notifications').select('*').eq('receiver_email', email).execute()
        # Access the data attribute of the response
        notifications = response.data
        return notifications
    except Exception as e:
        print(f"Error getting notifications: {e}")
        return None
    

def get_unread_notifications_count(receiver_email):
    try:
        response = supabase.table('notifications').select('*').eq('receiver_email', receiver_email).eq('status', 'unread').execute()
        # Access the data attribute of the response
        notifications = response.data
        return len(notifications) if notifications else 0
    except Exception as e:
        print(f"Error getting notifications count: {e}")
        return 0

def delete_notification(notification_id):
    """Delete a notification and return success status"""
    try:
        # Get the notification first to check its existence and type
        notification = supabase.table('notifications') \
            .select('*') \
            .eq('id_notification', notification_id) \
            .execute()
            
        if not notification.data:
            print(f"Notification {notification_id} not found")
            return False
            
        # Delete the notification
        result = supabase.table('notifications') \
            .delete() \
            .eq('id_notification', notification_id) \
            .execute()
            
        return True if result.data else False
    except Exception as e:
        print(f"Error deleting notification: {e}")
        return False
    
def get_notification_by_id(notification_id):
    try:
        notification = supabase.table('notifications') \
            .select('*') \
            .eq('id_notification', notification_id) \
            .execute()
    except Exception as e:
        print(f"Error getting notification: {e}")
        return None
    notification = notification.data[0] if notification.data else None
    return notification