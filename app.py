from flask import Flask, render_template, request, redirect, url_for, flash, session, g, render_template_string
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from helpers import *
from firebase_admin.firestore import FieldFilter
from flask import Flask, request, jsonify

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
        if role == 'customer':
            create_customer(username, email, password)                
        elif role == 'courier':
            create_courier(username, email, password)
        # elif role == 'admin':
        #     create_admin(username, email,  password)
        else:
            render_template_string('Invalid role. Please try again.')
        return render_template_string('success')
    return render_template('register.html')

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
    return redirect(url_for('login'))

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
        return render_template('/customer/create_order.html', segment='create_order')
    return redirect(url_for('login'))

@app.route('/dashboard/all_orders', methods=['GET'])
def all_orders():
    if g.admin:
        orders_ref = db.collection("orders").get()
        orders = [order.to_dict() for order in orders_ref]
        order_ids = [order.id for order in orders_ref] 
        courier_ref = db.collection("couriers").stream()
        couriers = [courier.id for courier in courier_ref]
        return render_template('/admin/all_orders.html', segment='all_orders', orders=orders, couriers=couriers, order_ids=order_ids)
    elif g.courier:
        orders = db.collection('orders').where('courier_id', '==', g.courier).get()
        orders = [order.to_dict() for order in orders]
        return render_template('/courier/all_orders.html', segment='all_orders', orders=orders)
    elif g.customer:
        orders_ref = db.collection('orders').where('user_id', '==', g.customer).get()
        orders = [order.to_dict() for order in orders_ref]
        order_ids = [order.id for order in orders_ref]
        return render_template('/customer/all_orders.html', segment='all_orders', orders=orders, order_ids=order_ids)
    
@app.route('/api/edit_order/<order_id>', methods=['POST'])
def edit_order(order_id):
    if g.customer or g.admin:
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
            return redirect(url_for('all_orders'))
    return redirect(url_for('login'))

@app.route('/api/edit_courier/<courier_id>', methods=['POST'])
def edit_courier(courier_id):
    if g.admin:
        if request.method == 'POST':
            phone = request.form['phone']
            email = request.form['email']
            db.collection('couriers').document(courier_id).update({'phone': phone, 'email': email})
            return redirect(url_for('manage_couriers'))
    return redirect(url_for('login'))

@app.route('/api/edit_customer/<customer_id>', methods=['POST'])
def edit_customer(customer_id):
    if g.admin:
        if request.method == 'POST':
            phone = request.form['phone']
            email = request.form['email']
            db.collection('customers').document(customer_id).update({'phone': phone, 'email': email})
            return redirect(url_for('manage_customers'))
    return redirect(url_for('login'))

@app.route('/api/delete_order/<order_id>', methods=['POST'])
def delete_order(order_id):
    if g.customer:
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
            order['tracking_history'][datetime.now().strftime("%m/%d/%Y, %H:%M:%S")] = {'status': status, 'location':location}
            order['status'] = status
            order['latitude'] = float(latitude)
            order['longitude'] = float(longitude)
            if status == "Delivered":
                order['delivery_date'] = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                order['delivered'] =  True
                order['avg_delivery_time'] = (datetime.strptime(order['delivery_date'], "%m/%d/%Y, %H:%M:%S") - datetime.strptime(order['pickup_date'], "%m/%d/%Y, %H:%M:%S")).total_seconds()/60
            elif status == "Pickup":
                order['pickup_date'] = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            elif status == "In Transit":
                order['in_transit_date'] = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            order_ref.update(order)
            customer_ref = db.collection('customers').document(order['user_id'])
            customer_noti = customer_ref.get().to_dict()
            customer_noti['notifications'][datetime.now().strftime("%m/%d/%Y, %H:%M:%S")] = {'message': f'Your order has been updated to {status}', 'read': False}
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
    if g.admin:  # Ensure that the user is an admin (you can adjust this as needed)
        data = request.get_json()

        order_id = data['order_id']
        courier_id = data['courier_id']

        order_ref = db.collection('orders').document(order_id)
        courier_ref = db.collection('couriers').document(courier_id)

        # Update the order to include the assigned courier_id
        order_ref.update({'status':'Order assigned Courier' ,'courier_id': courier_id, 'tracking_history': {datetime.now().strftime("%m/%d/%Y, %H:%M:%S"): {'status': 'Your order has been assigned to a courier', 'location':'N/A'}}})
        courier_ref.update({'deliveries':{'order_id': order_id}, 'notifications': {order_id: {'message': 'You have been assigned to a new delivery', 'timestamp': datetime.now(),'read': False}}})
        # notifications

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



# Additional routes and placeholders for various features
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.before_request
def before_request():
    g.customer, g.courier, g.admin,= None, None, None
    g.role = None
    if 'customer' in session:
        g.customer = session['customer']
        g.role = 'customer'
    elif 'courier' in session:
        g.courier = session['courier']
        g.role = 'courier'
    elif 'admin' in session:
        g.admin = session['admin']
        g.role = 'admin'

if __name__ == '__main__':
    app.run(debug=True)
