from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import os
import sqlite3
import json
from datetime import datetime
from utils import User, connect_db, authenticate_user, isCustomer, isRestaurant, getUserPostcode, restaurantName, insertAccountHolder, allowed_file, user_already_exists
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

app.secret_key = 'CleanDeSouza'

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.init_app(app)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# show user address and restaurant address in the order pagez


@login_manager.user_loader
def load_user(user_id):
  user = User()
  user.id = user_id
  return user


# route for logging in for both customer and restaurant
@app.route('/login', methods=['GET', 'POST'])
def login():

  if (current_user.is_authenticated):
    if (isCustomer()):
      postcode = getUserPostcode()
      return redirect(url_for('get_list_restaurants'))
    else:
      return redirect(url_for('restaurant_dashboard'))

  if request.method == 'POST':
    email = request.form['email']
    password = request.form['password']
    user = authenticate_user(email, password)

    if user:
      login_user(user)

      if isCustomer():
        print(int(current_user.id))
        postcode = getUserPostcode()
        return redirect(url_for('get_list_restaurants'))
      else:
        return render_template('restaurant_dashboard.html')
    else:
      print('flash here')
      flash('Login failed. Check your email and password.', 'error')
      return redirect(url_for('login'))
  return render_template('login.html')


# home page for the restaurant
@app.route('/restaurant_dashboard')
@login_required
def restaurant_dashboard():
  if (isRestaurant()):
    return render_template('restaurant_dashboard.html')
  else:
    return redirect(url_for('index'))


@app.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('index'))


@app.route('/')
def index():
  if (current_user.is_authenticated):
    return redirect(url_for('login'))
  return render_template('register.html')


@app.route('/register_customer', methods=['GET', 'POST'])
def register_customer():
  if request.method == 'POST':
    firstName = request.form['fname']
    lastName = request.form['lname']
    email = request.form['email']
    password = request.form['password']
    postcode = request.form['postcode']
    address = request.form['address']
    #session['name'] = request.form['name']

    conn = connect_db()
    if (user_already_exists(conn, email)):
      flash('Email already exists. Please use a different email.', 'error')
      conn.close()
      return redirect(url_for('register_customer'))

    last_row_id = insertAccountHolder(email, password, postcode, address, conn)

    conn.execute(
        'INSERT INTO Customer (CustomerID, FirstName, LastName) VALUES (?, ?, ?  )',
        (last_row_id, firstName, lastName))
    conn.commit()
    conn.close()
    return render_template('register_success.html')
  return render_template('register_customer.html')


@app.route('/register_restaurant', methods=['GET', 'POST'])
def register_restaurant():
  if request.method == 'POST':
    name = request.form['name']
    description = request.form['description']
    opening_time = request.form['opening_time']
    closing_time = request.form['closing_time']

    email = request.form['email']
    password = request.form['password']
    address = request.form['address']
    postcode = request.form['postcode']
    postcodes = request.form['postcodes']
    #session['name'] = request.form['name']
    postcodes_array = postcodes.split(',')

    conn = connect_db()
    if (user_already_exists(conn, email)):
      flash('Email already exists. Please use a different email.', 'error')
      conn.close()
      return redirect(url_for('register_restaurant'))

    if 'picture' in request.files:
      picture = request.files['picture']
      if picture and allowed_file(picture.filename):
        filename = secure_filename(picture.filename)
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
          os.makedirs(upload_folder)
        filename = f"{name}.jpeg"
        picture.save(os.path.join(upload_folder, filename))
      else:
        filename = "default restaurant.jpg"
    else:
      filename = "default restaurant.jpg"

    last_row_id = insertAccountHolder(email, password, postcode, address, conn)
    postcodes_array = [int(num) for num in postcodes_array]
    conn.execute(
        'INSERT INTO Restaurant (RestaurantID, OpeningTime, ClosingTime, Description, Picture, RestaurantName) VALUES (?, ?, ?,?,? ,? )',
        (last_row_id, opening_time, closing_time, description, filename, name))
    for item in postcodes_array:
      conn.execute(
          'INSERT INTO PostCodes (PostCode, RestaurantID) VALUES (?, ?)',
          (item, last_row_id))
    conn.commit()
    conn.close()
    print(name, description, email, password, address, postcode)
    return render_template('register_success.html')
  return render_template('register_restaurant.html')


#return list of restaurants for the customer
@app.route('/restaurant_list/')
@login_required
def get_list_restaurants():
  if isCustomer():
    conn = connect_db()
    current_time = datetime.now().strftime('%H:%M')

    rows = conn.execute(
        """SELECT Restaurant.*
							 FROM Restaurant 
							 JOIN PostCodes ON Restaurant.RestaurantID = PostCodes.RestaurantID 
							 JOIN AccountHolder ON AccountHolder.Postcode = PostCodes.Postcode 
							 WHERE AccountHolder.ID = ? 
								 AND ? BETWEEN Restaurant.OpeningTime AND Restaurant.ClosingTime""",
        (int(current_user.id), current_time)).fetchall()
    conn.close()

    restaurants = []
    for row in rows:
      restaurant_dict = dict(row)
      image_filename = restaurant_dict['Picture']
      image_path = url_for('static', filename=f'uploads/{image_filename}')
      restaurant_dict['image_path'] = image_path
      restaurants.append(restaurant_dict)

    return render_template('restaurant_list.html',
                           restaurants=restaurants,
                           postcode=getUserPostcode())
  else:
    return redirect(url_for('index'))


# endpoint for the restaurant to add an item to the menu
@app.route('/restaurant/add_to_menu', methods=['GET', 'POST'])
@login_required
def add_to_menu():
  if (isCustomer()):
    return redirect(url_for("index"))

  restaurant_id = current_user.id

  conn = connect_db()
  hasMenu = conn.execute('SELECT * FROM hasMenu WHERE RestaurantID = ?',
                         (int(restaurant_id), )).fetchall()
  menuId = 0
  if (len(hasMenu) == 0):
    print('no menu')
    menuId = conn.execute('INSERT INTO hasMenu(RestaurantID) VALUES(?)',
                          (restaurant_id, )).lastrowid
    conn.commit()
  else:
    menuId = conn.execute('SELECT  MenuID from hasMenu WHERE RestaurantID=?',
                          (restaurant_id, )).fetchone()['MenuID']

  menu_items = conn.execute(
      """SELECT Category.Name as category, Items.*   FROM Items 
  JOIN contains on Items.ItemID = contains.ItemID 
  JOIN Category on Category.CategoryID = Items.CategoryID
  where MenuId = ? and Items.isDeleted=0;""", (int(menuId), )).fetchall()

  if request.method == 'POST':
    item = request.form['item']
    category = request.form['category']
    price = request.form['price']
    description = request.form['description']

    if 'picture' in request.files:
      picture = request.files['picture']
      if picture and allowed_file(picture.filename):
        filename = secure_filename(picture.filename)
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
          os.makedirs(upload_folder)
        filename = f"{item}.jpeg"
        picture.save(os.path.join(upload_folder, filename))
      else:
        if category == '1':
          filename = "appetizer.jpg"
        elif category == '2':
          filename = "main.jpg"
        elif category == '3':
          filename = "dessert.jpg"
        elif category == '4':
          filename = "drink.jpg"
    else:
      if category == '1':
        filename = "appetizer.jpg"
      elif category == '2':
        filename = "main.jpg"
      elif category == '3':
        filename = "dessert.jpg"
      elif category == '4':
        filename = "drink.jpg"

    itemId = conn.execute(
        'INSERT INTO Items (ItemName, Picture, CategoryId, Price, ItemDescription, isDeleted) '
        'VALUES (?, ?, ?, ?, ?,?)',
        (item, filename, int(category), int(price), description, 0)).lastrowid

    conn.execute(
        'INSERT INTO contains (MenuID, ItemID) VALUES (?, ?)',
        (menuId, itemId),
    )

    conn.commit()
    conn.close()
    return redirect(url_for('add_to_menu'))
  conn.close()
  return render_template('restaurant_menu_add.html', items=menu_items)


#endpoint to see a restaurant's menu
@app.route('/menu/<restaurant_id>', methods=['GET', 'POST'])
@login_required
def menu_items(restaurant_id):
  if (isRestaurant()):
    return redirect(url_for("restaurant_dashboard"))

  session.modified = True
  session['restaurant_id'] = restaurant_id
  conn = connect_db()

  rows = conn.execute(
      """SELECT *  FROM contains 
  JOIN Items on Items.ItemID = contains.ItemID 
  JOIN hasMenu on hasMenu.MenuID = contains.MenuID
  JOIN Category on Category.CategoryId = Items.CategoryId
  where RestaurantID = ? and Items.isDeleted=0;""",
      (int(restaurant_id), )).fetchall()

  name = conn.execute(
      """SELECT RestaurantName from Restaurant where RestaurantID = ?""",
      (int(restaurant_id), )).fetchone()
  name = name['RestaurantName']
  menuItems = []
  for row in rows:
    menu_dict = dict(row)
    image_filename = menu_dict['Picture']
    image_path = url_for('static', filename=f'uploads/{image_filename}')
    menu_dict['image_path'] = image_path
    menuItems.append(menu_dict)

  conn.close()
  return render_template('menu_items_restaurant.html',
                         items=menuItems,
                         name=name)


#get the current user's cart
@app.route('/cart', methods=['GET', 'POST'])
@login_required
def cart():
  if (isRestaurant()):
    return redirect(url_for('restaurant_dashboard'))

  if (('cart' not in session) or
      ('total' not in session)) or ('additionalText' not in session):

    session['cart'] = []
    session['total'] = 0
    session['additionalText'] = None

  if request.method == "POST":
    items = request.form['items']
    total = request.form['total']
    additionalText = request.form['additionalText']

    if (items):
      session['cart'] = json.loads(items)
      session['total'] = total
      session['additionalText'] = additionalText

    else:
      session['cart'] = []

    return redirect(url_for("cart"))
  return render_template("cart.html",
                         cart=session['cart'],
                         total=session['total'],
                         additionalText=session['additionalText'])


@app.route('/item/edit/<item_id>', methods=['GET', 'POST'])
def editOrDeleteOrder(item_id):
  if (isCustomer()):
    return redirect(url_for('index'))

  conn = connect_db()
  item_data = conn.execute(
      """SELECT Items.ItemName as ItemName, Items.ItemID as item_id, Items.ItemDescription, Items.Price, Category.CategoryId as category, Category.Name as category_name FROM Items 
    JOIN Category on Category.CategoryID = Items.CategoryId
    WHERE ItemID = ?""", (item_id, )).fetchone()
  if request.method == 'POST':
    name = request.form['name']
    category = request.form['category']
    price = request.form['price']
    description = request.form['description']
    print(name, category, price, description)
    conn.execute(
        """UPDATE Items
     SET ItemName = ?, CategoryId = ?, Price = ?, ItemDescription = ? where ItemID=(?)""",
        (name, category, float(price), description, item_id))
    conn.commit()
    conn.close()
    return redirect(url_for('editOrDeleteOrder', item_id=item_id))

  conn.close()
  return render_template('edit_item.html',
                         item_id=item_id,
                         item_data=item_data)


@app.route("/item/delete/<item_id>")
def deleteItem(item_id):
  if (isCustomer()):
    return redirect(url_for('index'))

  conn = connect_db()
  conn.execute("UPDATE Items SET isDeleted = 1 WHERE ItemID = ?", (item_id, ))
  conn.commit()
  conn.close()
  return redirect(url_for('add_to_menu'))


  # send post request to the server to add an item to the cart
@app.route('/order_customer', methods=['GET', 'POST'])
@login_required
def order_customer():
  if (isRestaurant()):
    return redirect(url_for('restaurant_dashboard'))

  print(session['cart'], session['total'])
  conn = connect_db()

  items = session['cart']
  total = session['total']
  additionalText = session['additionalText']
  restaurant_id = session['restaurant_id']
  user_id = int(
      current_user.id)  #used as example. Please change user id when you login
  current_time = datetime.now()
  order_id = conn.execute(
      """INSERT INTO Orders(CustomerId, RestaurantId, 
      Status, AdditionalText, EstimatedDeliveryTime,             
      TotalCost, Order_Time) 
        VALUES(? , ? , ? , ? ,?, ? , ?)""",
      (user_id, restaurant_id, 'Processing', additionalText, '', total,
       current_time)).lastrowid

  for item in items:
    conn.execute(
        """INSERT INTO OrderItem(OrderId, ItemID, Quantity) VALUES(?, ?, ?)""",
        (order_id, item['item'], item['quantity']))

  conn.commit()
  conn.close()
  return render_template('menu_item_success.html')


# view all the orders for the customer
@app.route('/view_orders/customer')
@login_required
def view_orders_customer():
  if (isRestaurant()):
    return redirect(url_for("index"))

  conn = connect_db()
  customer_id = current_user.id
  processing_orders = conn.execute(
      """SELECT strftime('%d/%m/%Y %H:%M',Order_Time) as Order_Time, TotalCost, Status,OrderId from (
  SELECT * from Orders where CustomerId=(?) and Status='Processing' ORDER BY Order_Time DESC );""",
      (customer_id, )).fetchall()

  preparing_orders = conn.execute(
      """SELECT strftime('%d/%m/%Y %H:%M',Order_Time) as Order_Time, TotalCost, Status,OrderId from (
	SELECT * from Orders where CustomerId=(?) and Status='Preparing' ORDER BY Order_Time DESC );""",
      (customer_id, )).fetchall()

  completed_orders = conn.execute(
      """SELECT strftime('%d/%m/%Y %H:%M',Order_Time) as Order_Time, TotalCost, Status,OrderId from (
  SELECT * from Orders where CustomerId=(?) and Status='Complete' ORDER BY Order_Time DESC );""",
      (customer_id, )).fetchall()

  cancelled_orders = conn.execute(
      """SELECT strftime('%d/%m/%Y %H:%M',Order_Time) as Order_Time, TotalCost, Status,OrderId from (
  SELECT * from Orders where CustomerId=(?) and Status='Canceled' ORDER BY Order_Time DESC );""",
      (customer_id, )).fetchall()
  conn.close()
  return render_template('view_orders_customer.html',
                         processing_orders=processing_orders,
                         preparing_orders=preparing_orders,
                         completed_orders=completed_orders,
                         cancelled_orders=cancelled_orders)


# view a specific order for a customer
@app.route('/view_orders/customer/<order_id>')
@login_required
def view_order_customer(order_id):
  if (isRestaurant()):
    return redirect(url_for('restaurant_dashboard'))

  conn = connect_db()
  customer_id = current_user.id
  order_data = conn.execute(
      """SELECT Items.ItemName, OrderItem.Quantity, Items.Price, Orders.TotalCost, Restaurant.RestaurantName, AdditionalText

        FROM Orders
        JOIN OrderItem
        ON OrderItem.OrderId = Orders.OrderId
        JOIN Items
        ON Items.ItemId = OrderItem.ItemID
        JOIN Restaurant 
        ON Restaurant.RestaurantID = Orders.RestaurantId
        Where OrderItem.OrderId = ?
         AND Orders.CustomerId=?""", (int(order_id), customer_id)).fetchall()
  print()
  conn.close()
  return render_template('view_order_customer.html',
                         order_data=order_data,
                         total_cost=order_data[0]['TotalCost'],
                         restaurant_name=order_data[0]['RestaurantName'],
                         additionalText=order_data[0]['additionalText'])


# view all the orders of a restaurant
@app.route('/view_orders/restaurant')
@login_required
def view_orders():
  if (isCustomer()):
    return redirect(url_for("index"))

  conn = connect_db()
  restaurant_id = current_user.id
  # Processing -> Preparing -> Completed| Cancelled
  processing = conn.execute(
      """SELECT  TotalCost , OrderId, datetime(Order_Time) as Order_Time, Status FROM (
	SELECT * FROM Orders WHERE Orders.RestaurantId=(?) AND Status='Processing'
	ORDER by Order_Time desc);""", (restaurant_id, )).fetchall()
  preparing = conn.execute(
      """SELECT  TotalCost , OrderId, datetime(Order_Time) as Order_Time, Status FROM (
  SELECT * FROM Orders WHERE Orders.RestaurantId=(?) AND Status='Preparing'
  ORDER by Order_Time desc);""", (restaurant_id, )).fetchall()
  completed = conn.execute(
      """SELECT  TotalCost , OrderId, datetime(Order_Time) as Order_Time, Status FROM (
	SELECT * FROM Orders WHERE Orders.RestaurantId=(?) AND Status='Complete'
	ORDER by Order_Time desc);""", (restaurant_id, )).fetchall()
  canceled = conn.execute(
      """SELECT  TotalCost , OrderId, datetime(Order_Time) as Order_Time, Status FROM (
	SELECT * FROM Orders WHERE Orders.RestaurantId=(?) AND Status='Canceled'
	ORDER by Order_Time desc);""", (restaurant_id, )).fetchall()
  conn.close()
  return render_template('view_orders_restaurant.html',
                         processing=processing,
                         preparing=preparing,
                         completed=completed,
                         canceled=canceled)


# view and edit a  specific order from a restaurant's dashboard
@app.route('/order/edit/<order_id>', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
  if (isCustomer()):
    return redirect(url_for("index"))

  conn = connect_db()
  restaurant_id = current_user.id
  current_order = conn.execute(
      """SELECT Items.ItemName, OrderItem.Quantity, Orders.TotalCost, time(Orders.Order_Time) as Order_Time,
          AccountHolder.Address as user_address,
      Orders.Status, AdditionalText
      FROM Orders
        JOIN OrderItem
        ON OrderItem.OrderId = Orders.OrderId
        JOIN Items
        ON Items.ItemId = OrderItem.ItemID
        JOIN AccountHolder
        ON AccountHolder.ID = Orders.CustomerId 
        Where Orders.OrderId = ?
        AND Orders.RestaurantId=?""",
      (int(order_id), restaurant_id)).fetchall()
  total_cost = current_order[0]['TotalCost']
  order_time = (current_order[0]['Order_Time'])
  user_address = (current_order[0]['user_address'])
  addtional_text = (current_order[0]['AdditionalText'])
  if request.method == "POST":
    new_status = request.form.get('status')

    conn = connect_db()
    conn.execute(
        "UPDATE Orders SET Status = ? WHERE OrderId = ? AND RestaurantId = ?",
        (new_status, order_id, restaurant_id))
    conn.commit()
    conn.close()
    return redirect(url_for("view_orders"))

  conn.close()
  return render_template('edit_order.html',
                         current_order=current_order,
                         total_cost=total_cost,
                         user_address=user_address,
                         order_time=order_time,
                         addtional_text=addtional_text)


if __name__ == '__main__':
  app.run(debug=True, host='0.0.0.0', port=8080)
