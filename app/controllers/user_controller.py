from werkzeug.security import generate_password_hash, check_password_hash
from app.models import user as user_model
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app import supabase
import random
import time
from flask import session, request
import uuid


def create_user(id, email, name, surname, password, phone_number, birthday):
    if check_email_exists(email):
        return False
    
    try:
        # Inizia una transazione
        password_hash = generate_password_hash(password)
        user_data = {
            'id': id,
            'email': email,
            'name': name,
            'surname': surname,
            'password': password_hash,
            'phone_number': phone_number,
            'birthday': birthday,
        }
        
        # Inserisci l'utente
        user_response = supabase.table('user').insert(user_data).execute()
        
        if not user_response.data:
            return False
            
        # Crea il ruolo per l'utente
        role_data = {
            'user_id': id,
            'admin': False
        }
        
        # Inserisci il ruolo
        role_response = supabase.table('roles').insert(role_data).execute()
        
        if not role_response.data:
            # Se l'inserimento del ruolo fallisce, dovresti gestire il rollback
            # Elimina l'utente creato
            supabase.table('user').delete().eq('id', id).execute()
            return False
            
        return True
        
    except Exception as e:
        print(f"Error creating user: {e}")
        # In caso di errore, prova a fare rollback eliminando l'utente se esiste
        try:
            supabase.table('user').delete().eq('id', id).execute()
        except:
            pass
        return False

def login_user(email, password):
    try:
        response = supabase.table('user').select('email', 'password').eq('email', email).execute()
        if len(response.data) == 0:
            return None
        user = response.data[0]
        if check_password(user['password'], password):
            return user
        return None
    except Exception as e:
        print(f"Error logging in user: {e}")
        return None

def check_email_exists(email):
    try:
        response = supabase.table('user').select('email').eq('email', email).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error checking email: {e}")
        return False

def check_password(password_hash, password):
    return check_password_hash(password_hash, password)

def generate_verification_token():
    return random.randint(10000, 99999)

def send_verification_email(to_email):
    from_email = "ssb2024.2025@gmail.com"
    from_password = "vpon ryms zupv owmt"
    subject = "Email Verification"
    
    # Generate a new token
    token = generate_verification_token()
    body = f"Your new verification code is: {token}"

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        
        # Update stored token
        session['verification_token'] = {
            'token': str(token),
            'email': to_email,
            'timestamp': time.time()
        }
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def verify_token(token, email):
    stored_data = session.get('verification_token')
    attempts = session.get('verification_attempts', 0)
    
    if not stored_data:
        return False
    
    if attempts >= 2:
        # Reset token and attempts after 3 failed tries
        session.pop('verification_token', None)
        session.pop('verification_attempts', None)
        # Generate and send new token
        send_verification_email(email)
        return 'max_attempts'
        
    # Increment attempts
    session['verification_attempts'] = attempts + 1
        
    # Check if token is valid and not expired (2 minutes)
    if (stored_data['token'] == str(token) and 
        stored_data['email'] == email and 
        (time.time() - stored_data['timestamp']) < 120):
        session.pop('verification_token', None)
        session.pop('verification_attempts', None)
        return True
    return False

def get_user_by_email(email):
    try:
        response = supabase.table('user').select('*').eq('email', email).execute()
        if len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting user by email: {e}")
        return None

def get_user_by_id(user_id):
    try:
        response = supabase.table('user').select('*').eq('id', user_id).execute()
        if len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting user by id: {e}")
        return None

def get_companies_by_user_id(user_id):
    try:
        # Primo passo: ottenere i 'company_id' dalla tabella 'company_employe' per il dato 'user_id'
        response = supabase.table('company_employe').select('company_id').eq('user_id', user_id).execute()
        
        if len(response.data) > 0:
            company_ids = [item['company_id'] for item in response.data]  # Lista di 'company_id' associati all'utente
            
            # Secondo passo: usare i 'company_id' per ottenere i dettagli di tutte le compagnie dalla tabella 'companies'
            company_response = supabase.table('companies').select('*').in_('company_id', company_ids).execute()
            
            if len(company_response.data) > 0:
                return company_response.data  # Restituisce una lista di compagnie
            
        # Se non trovi nulla, restituisci None
        return None
    except Exception as e:
        print(f"Error getting companies by user id: {e}")
        return None




def get_user_role(user_id):
    """Get the role of a user"""
    try:
        response = supabase.table('roles').select('admin').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting user role: {e}")
        return None

def is_admin(user_id):
    """Check if user is admin"""
    try:
        response = supabase.table('roles').select('admin').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]['admin']
        return False
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return False

def is_company_admin(user_id):
    """Check if user is admin"""
    try:
        response = supabase.table('company_employe').select('company_admin').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]['company_admin']
        return False
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return False

def is_unique_company_admin(user_id):
    """Check if the user is the only company admin in their company"""
    try:
        # Ottieni l'azienda dell'utente
        response = supabase.table('company_employe').select('company_id', 'company_admin').eq('user_id', user_id).execute()
        
        if not response.data or not response.data[0]['company_admin']:
            return False  # L'utente non è un admin o non esiste

        company_id = response.data[0]['company_id']

        # Conta il numero di admin in questa azienda
        admin_count = supabase.table('company_employe').select('count', count='exact')\
            .eq('company_id', company_id).eq('company_admin', True).execute()

        if admin_count.count == 1:
            return True  # È l'unico admin dell'azienda
        return False  # Ci sono altri admin nella stessa azienda

    except Exception as e:
        print(f"Error checking unique admin status: {e}")
        return False
    
def get_company_ids_where_user_is_unique_admin(user_id):
    """Return the company_ids where the user is the only admin of the company"""
    try:
        # Ottieni tutte le compagnie in cui l'utente è un admin
        response = supabase.table('company_employe').select('company_id').eq('user_id', user_id).eq('company_admin', True).execute()
        
        if not response.data:
            return []  # Se l'utente non è amministratore in nessuna azienda, restituisci una lista vuota

        # Lista per raccogliere i company_id in cui l'utente è l'unico admin
        unique_admin_company_ids = []

        # Verifica per ogni compagnia
        for company in response.data:
            company_id = company['company_id']

            # Conta il numero di admin per questa compagnia
            admin_count = supabase.table('company_employe').select('count', count='exact')\
                .eq('company_id', company_id).eq('company_admin', True).execute()

            if admin_count.count == 1:  # Se l'utente è l'unico admin
                unique_admin_company_ids.append(company_id)

        return unique_admin_company_ids

    except Exception as e:
        print(f"Error getting unique admin company IDs: {e}")
        return []



def _get_ip_blocklist():
    """Get the IP blocklist from session"""
    return session.get('ip_blocklist', {})

def _update_ip_attempts(ip):
    
    """Update the IP attempts counter"""
    current_time = time.time()
    ip_blocklist = _get_ip_blocklist()
    
    # Clean up expired blocks
    ip_blocklist = {k: v for k, v in ip_blocklist.items() 
                   if current_time - v['timestamp'] < 30}
    
    if ip in ip_blocklist:
        ip_blocklist[ip]['attempts'] += 1
        ip_blocklist[ip]['timestamp'] = current_time
    else:
        ip_blocklist[ip] = {
            'attempts': 1,
            'timestamp': current_time
        }
    
    session['ip_blocklist'] = ip_blocklist
    return ip_blocklist[ip]['attempts']

def verify_login(email, password):
    try:
        # Check for IP-based blocking
        client_ip = request.remote_addr
        ip_blocklist = _get_ip_blocklist()
        current_time = time.time()
        
        if client_ip in ip_blocklist:
            block_info = ip_blocklist[client_ip]
            if block_info['attempts'] >= 3:
                # Check if 30 seconds have passed
                if current_time - block_info['timestamp'] < 60:
                    remaining_time = int(60 - (current_time - block_info['timestamp']))
                    return {'error': f'Too many failed attempts. Please wait {remaining_time} seconds.'}
                else:
                    # Reset attempts after timeout
                    del ip_blocklist[client_ip]
                    session['ip_blocklist'] = ip_blocklist

        # Verify credentials
        response = supabase.table('user').select('*').eq('email', email).execute()
        if len(response.data) == 0:
            attempts = _update_ip_attempts(client_ip)
            return None
            
        user = response.data[0]
        if check_password_hash(user['password'], password):
            # Reset IP attempts on successful login
            if client_ip in ip_blocklist:
                del ip_blocklist[client_ip]
                session['ip_blocklist'] = ip_blocklist
            return user
            
        # Update IP attempts
        attempts = _update_ip_attempts(client_ip)
        return None
        
    except Exception as e:
        print(f"Error verifying login: {e}")
        return None

def _update_failed_attempts(email):
    """Update the failed login attempts counter"""
    last_attempt = session.get('last_failed_login', {})
    current_time = time.time()
    
    if last_attempt.get('email') == email:
        session['last_failed_login'] = {
            'email': email,
            'attempts': last_attempt.get('attempts', 0) + 1,
            'timestamp': current_time
        }
    else:
        session['last_failed_login'] = {
            'email': email,
            'attempts': 1,
            'timestamp': current_time
        }

def update_user_info(user_id, field, value):
    try:
        response = supabase.table('user') \
            .update({field: value}) \
            .eq('id', user_id) \
            .execute()
        return response.data is not None
    except Exception as e:
        print(f"Error updating user info: {e}")
        return False

def generate_password_reset_token():
    """Generate a secure token for password reset"""
    return str(uuid.uuid4())  # Rimuovi il parametro email poiché non è necessario per generare il token

def send_password_reset_email(email, reset_token):
    from_email = "ssb2024.2025@gmail.com"
    from_password = "vpon ryms zupv owmt"
    subject = "Password Reset Request"
    
    # Create reset link with token
    reset_link = f"http://localhost:5000/password_recover_2/{reset_token}"
    
    html_content = f"""
    <html>
    <body>
        <h2>Password Reset Request</h2>
        <p>We received a request to reset your password. If you didn't make this request, please ignore this email.</p>
        <p>To reset your password, click the link below (valid for 10 minutes):</p>
        <p><a href="{reset_link}">Reset Password</a></p>
    </body>
    </html>
    """

    msg = MIMEMultipart('alternative')
    msg['From'] = from_email
    msg['To'] = email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending reset email: {e}")
        return False

def get_password_reset_attempts(ip):
    """Get the number of password reset attempts for an IP"""
    reset_attempts = session.get('password_reset_attempts', {})
    if ip in reset_attempts:
        if time.time() - reset_attempts[ip]['timestamp'] > 600:  # 10 minutes
            del reset_attempts[ip]
            session['password_reset_attempts'] = reset_attempts
            return 0
        return reset_attempts[ip]['attempts']
    return 0

def update_password_reset_attempts(ip):
    """Update password reset attempts for an IP"""
    reset_attempts = session.get('password_reset_attempts', {})
    current_time = time.time()
    
    if ip in reset_attempts:
        if current_time - reset_attempts[ip]['timestamp'] > 600:  # 10 minutes
            reset_attempts[ip] = {'attempts': 1, 'timestamp': current_time}
        else:
            reset_attempts[ip]['attempts'] += 1
    else:
        reset_attempts[ip] = {'attempts': 1, 'timestamp': current_time}
    
    session['password_reset_attempts'] = reset_attempts
    return reset_attempts[ip]['attempts']

def store_reset_token(email, token):
    """Store the reset token with timestamp and email"""
    # Recupera i token esistenti o inizializza un nuovo dizionario
    reset_tokens = session.get('reset_tokens', {})
    
    # Pulisci i token scaduti prima di aggiungerne uno nuovo
    current_time = time.time()
    reset_tokens = {
        k: v for k, v in reset_tokens.items() 
        if current_time - v['timestamp'] <= 600  # mantieni solo i token non scaduti (10 minuti)
    }
    
    # Aggiungi il nuovo token
    reset_tokens[token] = {
        'email': email,
        'timestamp': current_time
    }
    
    # Salva nella sessione
    session['reset_tokens'] = reset_tokens
    session.modified = True  # Forza il salvataggio della sessione
    
    print(f"Token stored: {token} for email: {email}")  # Debug print
    print(f"Current tokens after storing: {reset_tokens}")  # Debug print
    return token

def validate_reset_token(token):
    """Validate the reset token and return associated email if valid"""
    reset_tokens = session.get('reset_tokens', {})
    print(f"Current reset tokens during validation: {reset_tokens}")  # Debug print
    print(f"Validating token: {token}")  # Debug print
    
    if token in reset_tokens:
        token_data = reset_tokens[token]
        current_time = time.time()
        
        # Verifica che il token non sia scaduto (10 minuti) #600
        if current_time - token_data['timestamp'] <= 600:
            return token_data['email']
        else:
            # Rimuovi il token scaduto
            del reset_tokens[token]
            session['reset_tokens'] = reset_tokens
            session.modified = True  # Forza il salvataggio della sessione
            print(f"Token expired: {token}")  # Debug print
    return None

def update_user_password(email, new_password):
    """Update user's password"""
    try:
        password_hash = generate_password_hash(new_password)
        response = supabase.table('user') \
            .update({'password': password_hash}) \
            .eq('email', email) \
            .execute()
        return response.data is not None
    except Exception as e:
        print(f"Error updating password: {e}")
        return False

'''
def login_user(email, password):
    users = load_users_from_file()
    user = next((user for user in users if user['email'] == email), None)
    if user is None:
        return None
    if check_password(user['password_hash'], password):
        return user
    return None

def get_user_tokens(user_id):
    users = load_users_from_file()
    user = next((user for user in users if user['id'] == user_id), None)
    if user:
        return user.get('tokens', [])
    return []

def add_token_to_user(user_id, token):
    users = load_users_from_file()
    for user in users:
        if user['id'] == user_id):
            if 'tokens' not in user:
                user['tokens'] = []
            user['tokens'].append(token)
            save_users_to_file(users)
            return True
    return False
'''