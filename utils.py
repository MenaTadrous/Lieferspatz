from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])


def allowed_file(filename):
  return '.' in filename and filename.rsplit(
      '.', 1)[1].lower() in ALLOWED_EXTENSIONS


def connect_db():
  conn = sqlite3.connect('./lieferspatz.db')
  conn.row_factory = sqlite3.Row
  return conn


# write function where user already exists
class User(UserMixin):
  pass


def authenticate_user(email, password):
  conn = connect_db()
  user = conn.execute(
      'SELECT * FROM AccountHolder WHERE Email = ? AND Password = ?',
      (email, password)).fetchone()
  conn.close()
  if user:
    app_user = User()
    app_user.id = user['ID']
    return app_user
  conn.close()
  return None


def isCustomer():
  conn = connect_db()
  customer = conn.execute('SELECT *  FROM Customer where CustomerId = ?',
                          (int(current_user.id), )).fetchone()
  conn.close()
  if customer:
    return True
  conn.close()
  return False


def isRestaurant():
  conn = connect_db()
  restaurant = conn.execute('SELECT *  FROM Restaurant where RestaurantId = ?',
                            (current_user.id, )).fetchone()
  conn.close()
  if restaurant:
    return True
  conn.close()
  return False


def getUserPostcode():
  conn = connect_db()
  row = conn.execute('SELECT postcode FROM AccountHolder where ID = ?',
                     (int(current_user.id), )).fetchone()

  conn.close()
  return row['postcode']


def restaurantName():
  conn = connect_db()
  name = conn.execute('SELECT Name FROM Restaurant where RestaurantId = ?',
                      (current_user.id, )).fetchone()

  conn.close()
  return name


def insertAccountHolder(email, password, postcode, address, conn):
  account_holder = conn.execute(
      """INSERT INTO AccountHolder
      (Email, Password, postcode, Address) VALUES (?, ?, ? , ? )""",
      (email, password, postcode, address))
  last_row_id = account_holder.lastrowid
  return last_row_id


def user_already_exists(conn, email):

  user_exists = conn.execute('SELECT * FROM AccountHolder WHERE Email = ?',
                             (email, )).fetchone()
  print(user_exists)
  if user_exists:
    return True
  else:
    return False
