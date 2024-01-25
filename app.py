from flask import Flask, render_template, request, redirect, url_for, session, g, render_template_string
from datetime import datetime
from helpers import *
from firebase_admin.firestore import FieldFilter
from flask import Flask, request, jsonify
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Home Page - Display a list of users
@app.route('/')
def index():
    return render_template('/home/index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        if db.collection(role+'s').document(username).get().exists:
            user = db.collection(role+'s').document(username).get().to_dict()  # make sure to rename the collection in firestore to plural
            if check_password(password, user['password']):
                session[role] = username
                session['role'] = role
                return redirect(url_for('dashboard'))
            else:
                return render_template_string('Invalid password. Please try again.')
        return render_template_string('Invalid role. Please try again.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        streetAddress = request.form['streetAddress']
        line2address = request.form['line2address']
        city = request.form['city']
        state = request.form['state']
        country = request.form['country']
        phone = '+91'+request.form['phone']
        if role == 'customer':
            create_customer(username, email, password, streetAddress, line2address, city, state, country, phone)                
        elif role == 'courier':
            create_courier(username, email, password, streetAddress, line2address, city, state, country, phone)
        # elif role == 'admin':
        #     create_admin(username, email,  password)
        elif role == 'manager':
            create_manager(username, email, password, streetAddress, line2address, city, state, country, phone)
        else:
            render_template_string('Invalid role. Please try again.')
        return render_template_string('success')
    return render_template('register.html', GOOGLE_MAPS_API_KEY=os.getenv('GOOGLE_MAPS_API_KEY'), UT_API=os.getenv('UT_API'), UT_EMAIL=os.getenv('UT_EMAIL'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        if db.collection(role).document(username).get().exists:
            user = db.collection(role).document(username).get().to_dict()
            if user['email']:
                send_otp(username, role)
                return render_template('forgot_password.html', username=username, role=role, email=user['email'][3:])
            return render_template_string('Invalid email. Please try again.')
        return render_template_string('Invalid role. Please try again.')
    else:
        return render_template('forgot_password.html')

@app.route('/verify_otp', methods=['POST'])
def verify_otp_page():
    if request.method == 'POST':
        username = request.form.get('username')
        role = request.form.get('role')
        otp = request.form.get('otp')
        if verify_otp(username, role, otp):
            return render_template('reset_password.html', username=username, role=role)
        return render_template_string('Invalid OTP. Please try again.')

@app.route('/reset_password', methods=['POST'])
def reset_password():
    username = request.form['username']
    role = request.form['role']
    password = request.form['password']
    confirm_password = request.form['confirm_password']
    if password == confirm_password:
        if role == 'customers':
            update_customer_password(username, password)
        elif role == 'couriers':
            update_courier_password(username, password)
        elif role == 'admins':
            update_admin_password(username, password)
        return redirect(url_for('login'))
    return render_template_string('Passwords do not match. Please try again.')

# Dashboard
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if g.admin:
        no_couriers, no_customers, no_orders, no_orders_delivered, no_orders_pending, no_orders_in_transit = get_admin_dashboard_details()
        return render_template('/admin/dashboard.html', user=g.admin, segment='dashboard', no_couriers=no_couriers, no_customers=no_customers, no_orders=no_orders, no_orders_delivered=no_orders_delivered, no_orders_pending=no_orders_pending, no_orders_in_transit=no_orders_in_transit)
    elif g.courier:
        no_orders_delivered, no_orders_assigned, no_orders_in_transit = get_courier_dashboard_details(g.courier)
        return render_template('/courier/dashboard.html', user=g.courier, segment='dashboard', no_orders_delivered=no_orders_delivered, no_orders_assigned=no_orders_assigned, no_orders_in_transit=no_orders_in_transit)
    elif g.customer:
        no_orders_delivered, no_orders, no_orders_in_transit, new_notification = get_customer_dashboard_details(g.customer)
        return render_template('/customer/dashboard.html', user=g.customer, segment='dashboard', no_orders_delivered=no_orders_delivered, no_orders=no_orders, no_orders_in_transit=no_orders_in_transit, new_notification=new_notification)
    elif g.manager:
        order_ref = db.collection('orders').get()
        order_ids = [{'id':order.id, 'status':order.to_dict()['status']} for order in order_ref]
        return render_template('/manager/dashboard.html', user=g.manager, segment='dashboard', order_ids=order_ids)
    return redirect(url_for('login'))

@app.route('/profile')
def settings():
    if g.admin or g.customer or g.courier or g.manager:
        role = g.role
        username = g.get(role)
        data = db.collection(role+'s').document(username).get().to_dict()
        return render_template(role+'/profile.html', segment="profile", current_user={
            "username": username, "role": role, "data": data
        })
    return render_template('login.html')

# notifications for everyone
@app.route('/dashboard/notifications', methods=['GET'])
def notifications():
    if g.admin:
        notifications = db.collection('admins').document(g.admin).get().to_dict().get('notifications')
        return render_template('/admin/notifications.html',user=g.admin, segment='notifications', notifications=notifications)
    elif g.courier:
        notifications = db.collection('couriers').document(g.courier).get().to_dict().get('notifications')
        return render_template('/courier/notifications.html',user=g.courier,  segment='notifications', notifications=notifications)
    elif g.customer:
        notifications = db.collection('customers').document(g.customer).get().to_dict().get('notifications')
        return render_template('/customer/notifications.html',  user=g.customer, segment='notifications', notifications=notifications)
    return redirect(url_for('login'))

# Create a new order
@app.route('/dashboard/create_order', methods=['GET', 'POST'])
def create_order():
    if g.customer:
        print(g.customer)
        if request.method == 'POST':
            sender_name = request.form['sender_name']
            sender_address = request.form['sender_address']
            sender_contact = request.form['sender_contact']
            recipient_name = request.form['recipient_name']
            recipient_address = request.form['recipient_address']
            recipient_contact = request.form['recipient_contact']
            pickup_date = request.form['pickup_date']
            package_weight = request.form['package_weight']
            package_details = request.form['package_details']
            additional_notes = request.form['additional_notes']
            delivery_preference = request.form['delivery_preference']
            deliver_location = [request.form['latitude'], request.form['longitude']]
            user_id = g.customer
            order_created = create_customer_order(sender_name=sender_name, sender_contact=sender_contact, sender_address=sender_address, recipient_name=recipient_name, recipient_address=recipient_address, recipient_contact=recipient_contact, pickup_date=pickup_date, package_weight=package_weight, package_details=package_details, additional_notes=additional_notes, delivery_preference=delivery_preference, status='order ready for pickup', user_id=user_id, deliver_location=deliver_location)

            if order_created:
                return redirect(url_for('all_orders'))
            else:
                return render_template_string('Failed to create order. Please try again.')
        customer = db.collection('customers').document(g.customer).get().to_dict()
        return render_template('/customer/create_order.html', segment='create_order', customer=customer)
    return redirect(url_for('login'))

@app.route('/dashboard/all_orders', methods=['GET', 'POST'])
def all_orders():
    if g.admin:
        orders_ref = db.collection("orders").get()
        orders = [order.to_dict() for order in orders_ref]
        order_ids = [order.id for order in orders_ref] 
        courier_ref = db.collection("couriers").stream()
        couriers = [courier.id for courier in courier_ref]
        post = False
        if request.method == 'POST':
            post = True
        return render_template('/admin/all_orders.html', segment='all_orders', orders=orders, couriers=couriers, order_ids=order_ids, post=post)
    elif g.courier:
        orders = db.collection('orders').where('courier_id', '==', g.courier).get()
        orders = [order.to_dict() for order in orders]
        return render_template('/courier/all_orders.html', segment='all_orders', orders=orders)
    elif g.customer:
        orders_ref = db.collection('orders').where('user_id', '==', g.customer).get()
        orders = [order.to_dict() for order in orders_ref]
        order_ids = [order.id for order in orders_ref]
        return render_template('/customer/all_orders.html', segment='all_orders', orders=orders, order_ids=order_ids)
    elif g.manager:
        orders_ref = db.collection("orders").get()
        orders = [order.to_dict() for order in orders_ref]
        order_ids = [order.id for order in orders_ref] 
        courier_ref = db.collection("couriers").stream()
        couriers = [courier.id for courier in courier_ref]
        post = False
        if request.method == 'POST':
            post = True
        return render_template('/manager/all_orders.html', segment='all_orders', orders=orders, couriers=couriers, order_ids=order_ids, post=post, user=g.manager)

@app.route('/api/edit_order/<order_id>', methods=['POST'])
def edit_order(order_id):
    if g.customer or g.admin or g.manager:
        if request.method == 'POST':
            sender_name = request.form['sender_name']
            sender_address = request.form['sender_address']
            sender_contact = request.form['sender_contact']
            recipient_name = request.form['recipient_name']
            recipient_address = request.form['recipient_address']
            recipient_contact = request.form['recipient_contact']
            package_weight = request.form['package_weight']
            package_details = request.form['package_details']
            additional_notes = request.form['additional_notes']
            update_customer_order(order_id=order_id, sender_name=sender_name, sender_contact=sender_contact, sender_address=sender_address, recipient_name=recipient_name, recipient_address=recipient_address, recipient_contact=recipient_contact, package_weight=package_weight, package_details=package_details, additional_notes=additional_notes)
            return redirect(url_for('all_orders'), code=307)
    return redirect(url_for('login'))

@app.route('/api/edit_courier/<courier_id>', methods=['POST'])
def edit_courier(courier_id):
    if g.admin :
        if request.method == 'POST':
            phone = request.form['phone']
            email = request.form['email']
            db.collection('couriers').document(courier_id).update({'phone': phone, 'email': email})
            return redirect(url_for('manage_couriers'))
    return redirect(url_for('login'))

@app.route('/api/delete_courier/<courier_id>', methods=['POST'])
def delete_courier(courier_id):
    if g.admin :
        if request.method == 'POST':
            db.collection('couriers').document(courier_id).delete()
            return redirect(url_for('manage_couriers'))
    return redirect(url_for('login'))

@app.route('/api/edit_customer/<customer_id>', methods=['POST'])
def edit_customer(customer_id):
    if g.admin:
        if request.method == 'POST':
            phone = request.form['phone']
            email = request.form['email']
            streetAddress = request.form['streetAddress']
            city = request.form['city']
            state = request.form['state']
            country = request.form['country']
            address =  streetAddress+','+city+','+state+','+country
            db.collection('customers').document(customer_id).update({'phone': phone, 'email': email, 'streetAddress': streetAddress, 'city': city, 'state': state, 'country': country, 'address': address})
            return redirect(url_for('manage_customers'))
    return redirect(url_for('login'))

@app.route('/api/delete_customer/<customer_id>', methods=['POST'])
def delete_customer(customer_id):
    if g.admin:
        if request.method == 'POST':
            db.collection('customers').document(customer_id).delete()
            return redirect(url_for('manage_customers'))
    return redirect(url_for('login'))

@app.route('/api/edit_manager/<manager_id>', methods=['POST'])
def edit_manager(manager_id):
    if g.admin:
        if request.method == 'POST':
            phone = request.form['phone']
            email = request.form['email']
            db.collection('managers').document(manager_id).update({'phone': phone, 'email': email})
            return redirect(url_for('manage_managers'))
    return redirect(url_for('login'))

@app.route('/api/delete_manager/<manager_id>', methods=['POST'])
def delete_manager(manager_id):
    if g.admin:
        if request.method == 'POST':
            db.collection('managers').document(manager_id).delete()
            return redirect(url_for('manage_managers'))
    return redirect(url_for('login'))

@app.route('/api/delete_order/<order_id>', methods=['POST'])
def delete_order(order_id):
    if g.customer or g.admin:
        if request.method == 'POST':
            order_ref = db.collection("orders").document(order_id)
            order_ref.delete()
            return redirect(url_for('all_orders'))

# track order
@app.route('/dashboard/track_order', methods=['GET', 'POST'])
def track_order():
    if g.customer:
        orders = db.collection('orders').where(filter=FieldFilter('user_id', '==', g.customer)).where(filter=FieldFilter('status', '!=', 'order ready for pickup')).get()
        orders = [order.to_dict() for order in orders]
        return render_template('/customer/track_order.html', segment='track_order', orders=orders)
    return redirect(url_for('login'))

@app.route('/dashboard/update_delivery', methods=['GET', 'POST'])
def update_delivery():
    if g.courier:
        if request.method == 'POST':
            order_id = request.form['order_id']
            location = request.form['location']
            status = request.form['status']
            latitude = request.form['latitude']
            longitude = request.form['longitude']
            order_ref = db.collection('orders').document(order_id)
            order = order_ref.get().to_dict()
            now = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
            order['tracking_history'][now] = {'status': status, 'location':location}
            order['status'] = status
            order['latitude'] = float(latitude)
            order['longitude'] = float(longitude)
            if status == "Delivered":
                order['delivery_date'] = now
                order['delivered'] =  True
                order['avg_delivery_time'] = (datetime.strptime(order['delivery_date'], "%m/%d/%Y, %H:%M:%S") - datetime.strptime(order['pickup_date'], "%m/%d/%Y, %H:%M:%S")).total_seconds()/60
            elif status == "Pickup":
                order['pickup_date'] = now
            elif status == "In Transit":
                order['in_transit_date'] = now
            # logging
            if 'logs' in order:
                order['logs'][now] = {'message': g.courier+' updated order to '+status, 'location':location}
            else:
                order['logs'] = {now: {'message': g.courier+' updated order to '+status, 'location':location}}
            order_ref.update(order)
            customer_ref = db.collection('customers').document(order['user_id'])
            customer_noti = customer_ref.get().to_dict()
            customer_noti['notifications'][now] = {'message': f'Your order has been updated to {status}', 'read': False}
            # send_mail(order['user_id'], f'Your order has been updated to {status}', f'Your order has been updated to {status}')
            send_mail(username=order['user_id'], email=customer_noti['email'],subject=f'Your order has been updated to {status}', message=f'Your order has been updated to {status}')
            customer_ref.update(customer_noti)
                
        order_ref = db.collection('orders').where('courier_id', '==', g.courier).get()
        order_ids = [{'id':order.id, 'status':order.to_dict()['status']} for order in order_ref]
        return render_template('/courier/update_delivery.html', segment='update_delivery', order_ids=order_ids)
    else:
        return redirect(url_for('login'))

@app.route('/dashboard/map/<order_id>', methods=['GET'])
def map(order_id):
    if g.courier:
        order_ref = db.collection('orders').where('courier_id', '==', g.courier).get()
        order_ids = [order.id for order in order_ref]
        get_order = db.collection('orders').document(order_id).get().to_dict()
        longitude, latitude = get_order['deliver_location'][0], get_order['deliver_location'][1]
        return render_template('/courier/map.html', segment='map_route', order_id=order_id, latitude=latitude, longitude=longitude, order_ids=order_ids )
    return redirect(url_for('login'))

@app.route('/dashboard/map_route', methods=['GET'])
def map_route():
    if g.courier:
        order_ref = db.collection('orders').where('courier_id', '==', g.courier).get()
        order = [order.to_dict() for order in order_ref]
        order_ids = [order.id for order in order_ref]
        return render_template('/courier/map_route.html', segment='map_route', order=order, order_ref=order_ref, order_ids=order_ids)
    return redirect(url_for('login'))

@app.route('/assign_courier', methods=['POST'])
def assign_courier():
    if g.admin or g.manager:  # Ensure that the user is an admin (you can adjust this as needed)
        data = request.get_json()

        order_id = data['order_id']
        courier_id = data['courier_id']

        courier_ref = db.collection('couriers').document(courier_id)
        order_ref = db.collection('orders').document(order_id)
        order = order_ref.get().to_dict()
        now = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        # logging
        if 'logs' in order:
            order['logs'][now] = {'message': 'Order has been assigned to ' + courier_id}
        else:
            order['logs'] = {now: {'message': 'Order has been assigned to ' + courier_id}}        
        order['status'] = 'Order assigned Courier'
        order['courier_id'] = courier_id
        order['tracking_history'][now] =  {'status': 'Your order has been assigned to a courier', 'location':'N/A'}
        # new_order = order['logs']
        # new_order = {datetime.now().strftime("%d/%m/%Y, %H:%M:%S"): {'message':'Your order has been assigned to '+courier_id}}
        # order['logs'] = new_order
        # Update the order to include the assigned courier_id
        order_ref.update(order)
        # notifications
        courier_ref.update({'deliveries':{'order_id': order_id}, 'notifications': {order_id: {'message': 'You have been assigned to a new delivery', 'timestamp': datetime.now(),'read': False}}})
        customer_ref = db.collection('customers').document(order['user_id'])
        customer_noti = customer_ref.get().to_dict()
        send_mail(username=order['user_id'], email=customer_noti['email'],subject=f'Your order has been assigned to a courier', message=f'Your order has been assigned to a courier')
        

        return jsonify({'success': True}), 200
    else:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

@app.route('/dashboard/assigned_deliveries', methods=['GET'])
def assigned_deliveries():
    if g.courier:
        orders_ref = db.collection('orders').where(filter=FieldFilter('courier_id', '==', g.courier)).get()
        orders = [order.to_dict() for order in orders_ref]
        order_ids = [order.id for order in orders_ref]
        return render_template('/courier/assigned_deliveries.html', segment='assigned_deliveries', orders=orders, order_ids=order_ids)
    
@app.route('/dashboard/manage_couriers', methods=['GET'])
def manage_couriers():
    if g.admin:
        couriers_ref = db.collection('couriers').get()
        couriers = [courier.to_dict() for courier in couriers_ref]
        deliveries = [[courier.get('deliveries')] for courier in couriers]
        courier_ids = [courier.id for courier in couriers_ref]
        return render_template('/admin/manage_couriers.html', segment='manage_couriers', couriers=couriers, courier_ids=courier_ids, deliveries=deliveries)

@app.route('/dashboard/manage_customers', methods=['GET'])
def manage_customers():
    if g.admin:
        customers_ref = db.collection('customers').get()
        customers = [courier.to_dict() for courier in customers_ref]
        customer_ids = [courier.id for courier in customers_ref]
        return render_template('/admin/manage_customers.html', segment='manage_customers', customers=customers, customer_ids=customer_ids)

@app.route('/dashboard/manage_managers', methods=['GET'])
def manage_managers():
    if g.admin:
        managers_ref = db.collection('managers').get()
        managers = [manager.to_dict() for manager in managers_ref]
        manager_ids = [courier.id for courier in managers_ref]
        return render_template('/admin/manage_managers.html', segment='manage_managers', managers=managers, manager_ids=manager_ids)
    
@app.route('/api/update_delivery', methods=['POST'])
def api_update_delivery():
    if g.manager:
        order_id = request.form['order_id']
        status = request.form['status']
        order_ref = db.collection('orders').document(order_id)
        location = request.form['location']
        order = order_ref.get().to_dict()
        order['tracking_history'][datetime.now().strftime("%d/%m/%Y, %H:%M:%S")] = {'status': status, 'location':location}
        order['status'] = status
        now = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        # logging
        if 'logs' in order:
            order['logs'][now] = {'message': g.manager+' updated order to '+status, 'location':location}
        else:
            order['logs'] = {now: {'message': g.manager+' updated order to '+status, 'location':location}}
        order_ref.update(order)
        customer_ref = db.collection('customers').document(order['user_id'])
        customer_noti = customer_ref.get().to_dict()
        customer_noti['notifications'][datetime.now().strftime("%d/%m/%Y, %H:%M:%S")] = {'message': f'Your order has been updated to {status}', 'read': False}
        send_mail(username=order['user_id'], email=customer_noti['email'],subject=f'Your order has been updated to {status}', message=f'Your order has been updated to {status}')
        customer_ref.update(customer_noti)
        return redirect(url_for('dashboard'))

@app.route('/dashboard/logs', methods=['GET'])
def logs():
    if g.admin:
        orders_ref = db.collection('orders').get()
        orders = [order.to_dict() for order in orders_ref]
        order_ids = [order.id for order in orders_ref]
        return render_template('/admin/logs.html', segment='logs', orders=orders, order_ids=order_ids, user=g.admin)
    elif g.manager:
        orders_ref = db.collection('orders').get()
        orders = [order.to_dict() for order in orders_ref]
        order_ids = [order.id for order in orders_ref]
        return render_template('/manager/logs.html', segment='logs', orders=orders, order_ids=order_ids)

@app.route('/dashboard/support', methods=['GET', 'POST'])
def support():
    if request.method == 'POST':
        support_type = request.form['support_type']
        support_description = request.form['support_description']
        order_id = request.form['order_id']
        order_ref = db.collection('orders').document(order_id)
        order = order_ref.get().to_dict()
        now = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        # logging
        if 'logs' in order:
            order['logs'][now] = {'message': 'Support ticket created by Customer', 'location':'N/A'}
        else:
            order['logs'] = {now: {'message': 'Support ticket created by Customer', 'location':'N/A'}}
        if 'support' in order:
            order['support'][now] = {'support_type': support_type, 'support_description': support_description}
        else:
            order['support'] = {now: {'support_type': support_type, 'support_description': support_description}}
        order['ticket_created'] = True
        order_ref.update(order)
        customer_ref = db.collection('customers').document(order['user_id'])
        customer_noti = customer_ref.get().to_dict()
        customer_noti['notifications'][now] = {'message': f'Your support ticket has been created', 'read': False}
        send_mail(username=order['user_id'], email=customer_noti['email'],subject=f'Your support ticket has been created', message=f'Your support ticket has been created')
        customer_ref.update(customer_noti)
        return redirect(url_for('support'))
    else:
        if g.admin:
            orders_ref = db.collection('orders').where(filter=FieldFilter('ticket_created', '==', True)).get()
            orders = [order.to_dict() for order in orders_ref]
            order_ids = [order.id for order in orders_ref]
            return render_template('/admin/support.html', segment='support', user=g.admin, orders=orders, order_ids=order_ids)
        elif g.manager:
            orders_ref = db.collection('orders').where(filter=FieldFilter('ticket_created', '==', True)).get()
            orders = [order.to_dict() for order in orders_ref]
            order_ids = [order.id for order in orders_ref]
            return render_template('/manager/support.html', segment='support', user=g.manager, orders=orders, order_ids=order_ids)
        elif g.customer:
            order_ref = db.collection('orders').where('user_id', '==', g.customer).get()
            order_ids = [order.id for order in order_ref]
            support_logs  = [order.to_dict().get('support') for order in order_ref]
            return render_template('/customer/select_support_order.html', segment='support', user=g.customer, order_ids=order_ids, support_logs=support_logs)

@app.route('/api/support/reply', methods=['POST'])
def api_support_reply():
    data = request.get_json()
    support_type = data['support_type']
    support_description = data['support_description']
    order_id = data['order_id']
    timestamp = data['timestamp']
    order_ref = db.collection('orders').document(order_id)
    order = order_ref.get().to_dict()
    
    # logging
    if 'logs' in order:
        order['logs'][timestamp] = {'message': 'Customer has replied to the Support Ticket', 'location':'N/A'}
    else:
        order['logs'] = {timestamp: {'message': 'Customer has replied to the Support Ticket', 'location':'N/A'}}
    if 'support' in order:
        order['support'][timestamp] = {'support_type': support_type, 'support_description': support_description}
    else:
        order['support'] = {timestamp: {'support_type': support_type, 'support_description': support_description}}
    order['ticket_created'] = True
    order_ref.update(order)
    
    return jsonify({'message': 'Message sent successfully'}), 200

@app.route('/api/update_ticket', methods=['POST'])
def api_update_ticket():
    if g.manager:
        order_id = request.form['order_id']
        support = request.form['support']
        order_ref = db.collection('orders').document(order_id)
        order = order_ref.get().to_dict()
        now = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        # logging
        if 'logs' in order:
            order['logs'][now] = {'message': g.manager+' updated support ticket', 'location':'N/A'}
        else:
            order['logs'] = {now: {'message': g.manager+' updated support ticket', 'location':'N/A'}}
        if 'support' in order:
            order['support'][now] = {'support': support}
        else:
            order['support'] = {now: {'support': support}}
        order_ref.update(order)
        customer_ref = db.collection('customers').document(order['user_id'])
        customer_noti = customer_ref.get().to_dict()
        customer_noti['notifications'][now] = {'message': f'Your support ticket has been updated!\n {support}', 'read': False}
        send_mail(username=order['user_id'], email=customer_noti['email'],subject=f'Your support ticket has been updated', message=f'Your support ticket has been updated')
        customer_ref.update(customer_noti)
        return redirect(url_for('dashboard'))
    elif g.admin:
        order_id = request.form['order_id']
        support = request.form['support']
        order_ref = db.collection('orders').document(order_id)
        order = order_ref.get().to_dict()
        now = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        # logging
        if 'logs' in order:
            order['logs'][now] = {'message': g.admin+' responded support ticket', 'location':'N/A'}
        else:
            order['logs'] = {now: {'message': g.admin+' responded support ticket', 'location':'N/A'}}
        # if 'support' in order:
        #     order['support'][now] = {'support': support}
        # else:
        #     order['support'] = {now: {'support': support}}
        order_ref.update(order)
        customer_ref = db.collection('customers').document(order['user_id'])
        customer_noti = customer_ref.get().to_dict()
        customer_noti['notifications'][now] = {'message': f'Your support ticket has been updated!\n {support}', 'read': False}
        send_mail(username=order['user_id'], email=customer_noti['email'],subject=f'Your support ticket has been updated', message=f'Your support ticket has been updated')
        customer_ref.update(customer_noti)
        return redirect(url_for('dashboard'))

# Additional routes and placeholders for various features
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.before_request
def before_request():
    g.customer, g.courier, g.admin, g.manager= None, None, None, None
    g.role = None
    if 'customer' in session:
        g.customer = session['customer']
        g.role = 'customer'
    elif 'courier' in session:
        g.courier = session['courier']
        g.role = 'courier'
    elif 'manager' in session:
        g.manager = session['manager']
        g.role = 'manager'
    elif 'admin' in session:
        g.admin = session['admin']
        g.role = 'admin'

if __name__ == '__main__':
    app.run(debug=True)
