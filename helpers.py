from models import db
import bcrypt
from datetime import datetime
from firebase_admin.firestore import FieldFilter


def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'),bcrypt.gensalt(8))

def check_password(password, hashed_password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)
    

def create_courier( username, email, password, notifications={}):
    courier_ref = db.collection("couriers").document(username)
    if not courier_ref.get().exists:
        courier_data = {
            "username": username,
            "email": email,
            "password": hash_password(password), 
            "notifications": notifications, 
            "avg_time": "0",
        }
        courier_ref.set(courier_data)
    else:
        print("Courier already exists")
        return False

# Define a function to create a document for Customer
def create_customer(username, email, password, notifications={}):
    customer_ref = db.collection("customers").document(username)
    if not customer_ref.get().exists:
        customer_data = {
            "username": username,
            "email": email,
            "password": hash_password(password),  
            "notifications": notifications
        }
        customer_ref.set(customer_data)
    else:
        print("Customer already exists")
        return False

# Define a function to create a document for Admin
def create_admin(username, email, password, notifications={}):
    admin_ref = db.collection("admins").document(username)
    if not admin_ref.get().exists:
        admin_data = {
            "email": email,
            "username": username,
            "password": hash_password(password),  
            "notifications": notifications,
        }
        admin_ref.set(admin_data)
    else:
        print("Admin already exists")
        return False
# Define a function to create a document for Orders
def create_customer_order(sender_name, sender_contact, sender_address, recipient_name, recipient_address, recipient_contact, pickup_date, package_weight, package_details, additional_notes, delivery_preference, status, user_id, deliver_location, tracking_history={}):
    order_data = {
        "sender_name": sender_name,
        "sender_contact" : sender_contact,
        "sender_address": sender_address,
        "recipient_name": recipient_name,
        "recipient_address": recipient_address,
        "recipient_contact" : recipient_contact,
        "pickup_date": pickup_date,
        "package_weight": package_weight,
        "package_details": package_details,
        "additional_notes": additional_notes,
        "delivery_preference": delivery_preference,
        "status": status,
        "delivered" : False,
        "deliver_location": deliver_location,
        "user_id": user_id,
        "tracking_history": tracking_history
    }
    update_time, order_ref = db.collection("orders").add(order_data)
    return order_ref.id

# Admin Dashboard
def get_admin_dashboard_details():
        db_couriers = db.collection('couriers')
        db_customers = db.collection('customers')
        db_orders = db.collection('orders')
        no_couriers = len(db_couriers.get())
        no_customers = len(db_customers.get())
        no_orders = len(db_orders.get())
        no_orders_delivered = len(db_orders.where(filter=FieldFilter('status', '==', 'Delivered')).get())
        no_orders_pending = len(db_orders.where(filter=FieldFilter('status', '==', 'Order assigned Courier')).get())
        no_orders_in_transit = len(db_orders.where(filter=FieldFilter('status', '==', 'In Transit')).get())
        return [no_couriers, no_customers, no_orders, no_orders_delivered, no_orders_pending, no_orders_in_transit]

def get_courier_dashboard_details(courier_id):
        db_orders = db.collection('orders').where(filter=FieldFilter('courier_id', '==', courier_id))
        no_orders_assigned = len(db_orders.get())
        no_orders_delivered = len(db_orders.where(filter=FieldFilter('status', '==', 'Delivered')).get())
        no_orders_in_transit = len(db_orders.where(filter=FieldFilter('status', '==', 'In Transit')).get())
        return [no_orders_delivered, no_orders_assigned, no_orders_in_transit]
# Get all couriers
def get_all_couriers():
    couriers_ref = db.collection("couriers").stream()
    return [courier.to_dict() for courier in couriers_ref]

# Get all customers
def get_all_customers():
    customers_ref = db.collection("customers").stream()
    return [customer.to_dict() for customer in customers_ref]

# Get all admins
def get_all_admins():
    admins_ref = db.collection("admins").stream()
    return [admin.to_dict() for admin in admins_ref]

# Get all notifications for a specific user
def get_user_notifications(username):
    user_ref = db.collection("users").document(username)
    return user_ref.get().to_dict().get("notifications", {})

# Update user profile information (e.g., email)
def update_user_profile(username, updated_data):
    user_ref = db.collection("users").document(username)
    user_ref.update(updated_data)

# Assign an order to a courier
def assign_order_to_courier(order_id, courier_username):
    order_ref = db.collection("orders").document(order_id)
    order_ref.update({"courier_username": courier_username})

# Retrieve orders assigned to a specific courier
def get_orders_assigned_to_courier(courier_username):
    orders_ref = db.collection("orders").where("courier_username", "==", courier_username).stream()
    return [order.to_dict() for order in orders_ref]

def get_customer_order(order_id):
    order_ref = db.collection("orders").document(order_id)
    return order_ref.get().to_dict()

def update_customer_order(order_id, sender_name, sender_contact, sender_address, recipient_name, recipient_address, recipient_contact, package_weight, package_details, additional_notes):
    order_ref = db.collection("orders").document(order_id)
    order_ref.update({"sender_name": sender_name, "sender_contact": sender_contact, "sender_address": sender_address, "recipient_name": recipient_name, "recipient_address": recipient_address, "recipient_contact": recipient_contact, "package_weight": package_weight, "package_details": package_details, "additional_notes": additional_notes})

# Update the status of an order
def update_order_status(order_id, new_status):
    order_ref = db.collection("orders").document(order_id)
    order_ref.update({"status": new_status})

# Create a new notification for a user
def create_notification(username, notification_id, message, timestamp, read=False):
    user_ref = db.collection("users").document(username)
    notifications = user_ref.get().to_dict().get("notifications", {})
    notifications[notification_id] = {
        "message": message,
        "timestamp": timestamp,
        "read": read
    }
    user_ref.update({"notifications": notifications})

# Mark a notification as read
def mark_notification_as_read(username, notification_id):
    user_ref = db.collection("users").document(username)
    notifications = user_ref.get().to_dict().get("notifications", {})
    if notification_id in notifications:
        notifications[notification_id]["read"] = True
        user_ref.update({"notifications": notifications})

# Delete a notification
def delete_notification(username, notification_id):
    user_ref = db.collection("users").document(username)
    notifications = user_ref.get().to_dict().get("notifications", {})
    if notification_id in notifications:
        del notifications[notification_id]
        user_ref.update({"notifications": notifications})

# Get all orders for a specific user (courier or customer) by their username
def get_orders_by_user(username):
    orders_ref = db.collection("orders").where("user_id", "==", username).stream()
    return [order.to_dict() for order in orders_ref]

# Get all orders in a specific status (e.g., "In Transit" or "Delivered")
def get_orders_by_status(status):
    orders_ref = db.collection("orders").where("status", "==", status).stream()
    return [order.to_dict() for order in orders_ref]

# Create a new tracking history entry for an order
def create_tracking_history(order_id, timestamp, location, status):
    order_ref = db.collection("orders").document(order_id)
    tracking_history = order_ref.get().to_dict().get("tracking_history", {})
    tracking_history[timestamp] = {
        "location": location,
        "status": status
    }
    order_ref.update({"tracking_history": tracking_history})

# Add a notification for a specific user
def add_notification(username, notification_data):
    user_ref = db.collection("users").document(username)
    notifications = user_ref.get().to_dict().get("notifications", {})
    notification_id = notification_data.get("notification_id")
    notifications[notification_id] = notification_data
    user_ref.update({"notifications": notifications})

# Delete an order document
def delete_order(order_id):
    order_ref = db.collection("orders").document(order_id)
    order_ref.delete()

# Get all orders for a specific courier
def get_orders_by_courier(courier_username):
    orders_ref = db.collection("orders").where("courier_username", "==", courier_username).stream()
    return [order.to_dict() for order in orders_ref]

# Calculate delivery statistics for a courier
def calculate_courier_statistics(courier_username):
    orders = get_orders_by_courier(courier_username)
    total_orders = len(orders)
    delivered_orders = sum(1 for order in orders if order["status"] == "Delivered")
    pending_orders = sum(1 for order in orders if order["status"] == "Pending")
    transit_orders = total_orders - delivered_orders - pending_orders
    return {
        "total_orders": total_orders,
        "delivered_orders": delivered_orders,
        "pending_orders": pending_orders,
        "transit_orders": transit_orders,
    }

# Calculate system-wide delivery statistics
def calculate_system_statistics():
    orders_ref = db.collection("orders").stream()
    total_orders = 0
    delivered_orders = 0
    pending_orders = 0
    for order in orders_ref:
        order_data = order.to_dict()
        total_orders += 1
        if order_data["status"] == "Delivered":
            delivered_orders += 1
        elif order_data["status"] == "Pending":
            pending_orders += 1
    transit_orders = total_orders - delivered_orders - pending_orders
    return {
        "total_orders": total_orders,
        "delivered_orders": delivered_orders,
        "pending_orders": pending_orders,
        "transit_orders": transit_orders,
    }

# Calculate order volume statistics for a specific time period
def calculate_order_volume(start_date, end_date):
    orders_ref = db.collection("orders").where("timestamp", ">=", start_date).where("timestamp", "<=", end_date).stream()
    return len(list(orders_ref))

def getDuration(then, now = datetime.now(), interval = "default"):

    # Returns a duration as specified by variable interval
    # Functions, except totalDuration, returns [quotient, remainder]

    duration = now - then # For build-in functions
    duration_in_s = duration.total_seconds() 
    
    def years():
      return divmod(duration_in_s, 31536000) # Seconds in a year=31536000.

    def days(seconds = None):
      return divmod(seconds if seconds != None else duration_in_s, 86400) # Seconds in a day = 86400

    def hours(seconds = None):
      return divmod(seconds if seconds != None else duration_in_s, 3600) # Seconds in an hour = 3600

    def minutes(seconds = None):
      return divmod(seconds if seconds != None else duration_in_s, 60) # Seconds in a minute = 60

    def seconds(seconds = None):
      if seconds != None:
        return divmod(seconds, 1)   
      return duration_in_s

    def totalDuration():
        y = years()
        d = days(y[1]) # Use remainder to calculate next variable
        h = hours(d[1])
        m = minutes(h[1])
        s = seconds(m[1])

        return "Time between dates: {} years, {} days, {} hours, {} minutes and {} seconds".format(int(y[0]), int(d[0]), int(h[0]), int(m[0]), int(s[0]))

    return {
        'years': int(years()[0]),
        'days': int(days()[0]),
        'hours': int(hours()[0]),
        'minutes': int(minutes()[0]),
        'seconds': int(seconds()),
        'default': totalDuration()
    }[interval]
# track pickup time vs delivery time
"""

In [6]: print(getDuration(then)) # E.g. Time between dates: 7 years, 208 days, 21 hours, 19 minutes and 15 seconds
   ...: print(getDuration(then, now, 'years'))      # Prints duration in years
   ...: print(getDuration(then, now, 'days'))       #                    days
   ...: print(getDuration(then, now, 'hours'))      #                    hours
   ...: print(getDuration(then, now, 'minutes'))    #                    minutes
   ...: print(getDuration(then, now, 'seconds'))
Time between dates: 11 years, 198 days, 13 hours, 24 minutes and 5 seconds
11
4213
101125
6067524
364051452

In [7]: then
Out[7]: datetime.datetime(2012, 3, 5, 23, 8, 15)

In [8]: datetime.now()
Out[8]: datetime.datetime(2023, 9, 18, 12, 50, 13, 139902)

In [9]: getDuration(datetime.now())
Out[9]: 'Time between dates: -1 years, 364 days, 23 hours, 41 minutes and 52 seconds'

In [10]: getDuration(datetime.now(),datetime.now())
Out[10]: 'Time between dates: 0 years, 0 days, 0 hours, 0 minutes and 0 seconds'

In [11]: getDuration(now ,datetime.now())
Out[11]: 'Time between dates: 0 years, 0 days, 0 hours, 18 minutes and 23 seconds'

In [12]: str(datetime.now())
Out[12]: '2023-09-18 12:51:03.350994'

In [29]: str(datetime.now())
Out[29]: '2023-09-18 12:56:49.412708'

In [30]: datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')
Out[30]: '2023-09-18 12:58:18'

In [31]: date_str = datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')

In [32]: date_format = '%Y-%m-%d %H:%M:%S'

In [33]: date_obj = datetime.strptime(date_str, date_format)

In [34]: date_obj
Out[34]: datetime.datetime(2023, 9, 18, 12, 58, 28)

In [35]: str(date_obj)
Out[35]: '2023-09-18 12:58:28'

"""