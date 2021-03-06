#!/usr/bin/env python3
"""
Columbia's COMS W4111 Introduction to Databases
Webserver

To run locally:

    python server.py

Go to http://localhost:8111 in your browser.

A debugger such as "pdb" may be helpful for debugging.

@author: CodingCow
"""

import os
from datetime import datetime
from sqlalchemy import *
# from sqlalchemy.sql import func
# from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, url_for
from flask_login import LoginManager, login_required, login_user, logout_user, current_user

# Import custom modules
from user_class import User



# ============================================================
# Create app and setup database
# ============================================================
tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

#
# Enable flask-login
#
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

#
# XXX: The URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@104.196.152.219/proj1part2
#



#
# Creates a database engine that knows how to connect to the URI above.
#
engine = create_engine(DATABASEURI)

#
#
# Access the local website at 
#
#   http://localhost:8111/
# 
#

#
# Constructor and deconstructor
# 
@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request 
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request.
    
    The variable g is globally accessible.
    """
    try:
        g.conn = engine.connect()
    except:
        print("uh oh, problem connecting to database")
        import traceback; traceback.print_exc()
        g.conn = None


@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't, the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception: #  as e
        pass



# ============================================================
#   MAIN PAGE
# ============================================================
@app.route('/')
def index():
    """
    request is a special object that Flask provides to access web request information:
    
    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2
    
    See its API: http://flask.pocoo.org/docs/0.10/api/#incoming-request-data
    """

    # DEBUG: this is debugging code to see what request looks like
    # print(request.args)

    if current_user.is_authenticated:
        return redirect(url_for('main'))

    # render_template looks in the templates/ folder for files.
    # for example, the below file reads template/index.html
    return render_template("index.html")


# === Main page after log in ===
@app.route('/main', methods=['GET', 'POST'])
@login_required
def main():

    # ============= Query: Product =================#
    # ============================================#

    product = []
    print(request.form)
    if bool(request.form):
        pproductname = None if not request.form['pproductname'] else request.form['pproductname']

        pprice = None if not request.form['pprice'] else int(request.form['pprice'])

        pcategory = None if not request.form['pcategory'] else request.form['pcategory']

        cursor = g.conn.execute(
            "SELECT DISTINCT p.* FROM product p, belong b, category c \
                WHERE (%s IS NULL OR p.productname = %s) AND (%s IS NULL OR p.price = %s)\
                    AND (%s IS NULL OR (c.categoryid=b.categoryid AND c.categoryname=%s AND b.productid=p.productid))",
            pproductname, pproductname, pprice, pprice, pcategory, pcategory)
        product = cursor.fetchall()
        cursor.close()
        
    else:
        # Show all by default
        cursor = g.conn.execute("SELECT * FROM product")
        product = cursor.fetchall()
        cursor.close()


    # ============= Query: Supplier ================= #
    # ============================================ #

    cursor = g.conn.execute(
        "SELECT s.productid, s.supplierid, s.suppliername, p.productname FROM supplier s, product p WHERE s.productid = p.productid")
    supplier = []
    supplier = cursor.fetchall()
    cursor.close()


    # =========== Supplier transaction ================= #
    # ================================================= #

    # Query this supplier's transaction date

    cursor = g.conn.execute("SELECT DISTINCT p.productid, p.productname, s.suppliername, s.supplierid, Pr.cost, to_char(Pr.providedate, 'Month DD, YYYY') FROM product p, supplier s, provide Pr WHERE p.productid = Pr.productid AND Pr.supplierid=s.supplierid")
    supplier_transaction = []
    supplier_transaction = cursor.fetchall()
    cursor.close()


    # ============= Reviews/Rating ======================= #
    # =============================================== #

    # Query Reviews for each product, from each user
    cursor = g.conn.execute("SELECT p.productid, p.productname, r.ratings, r.ratingtitle, r.loved, c.customerid FROM product p, rating r, customer c WHERE p.productid = r.productid AND c.customerid = r.customerid ORDER BY r.customerid DESC")
    product_reviews = []
    product_reviews = cursor.fetchall()
    cursor.close()

    # Query Review Average for ONE PRODUCT
    cursor = g.conn.execute("SELECT p.productid, p.productname, ROUND(AVG(r.ratings),2) FROM product p, rating r WHERE p.productid = r.productid GROUP BY p.productid")
    product_ratings = []
    product_ratings = cursor.fetchall()
    cursor.close()


    # =============== Category ======================== #
    # ================================================ #

    # Query: Category
    cursor = g.conn.execute("SELECT b.categoryid, b.productid, p.productname, c.categoryname FROM belong b, category c, product p WHERE p.productid=b.productid AND c.categoryid=b.categoryid")
    category = []
    category = cursor.fetchall()
    cursor.close()


    # Summary
    # ================================================ #
    
    context = dict(
        product=product,
        supplier=supplier,
        supplier_transaction=supplier_transaction,
        product_reviews=product_reviews,
        product_ratings=product_ratings,
        category=category
        )

    return render_template("main.html", **context)


# Action writing review in main page
@app.route('/write_review', methods=['POST'])
def write_review():
    customerid = current_user.uid

    # PostgreSQL 9.5
    result = g.conn.execute(
        "UPDATE rating SET ratingid=%s, ratings=%s, loved=%s, ratingtitle=%s WHERE productid=%s AND customerid=%s", 
        request.form['rid'], request.form['rating'], request.form['loved'], request.form['text'], request.form['pid'], customerid)

    if result.rowcount == 0:
        g.conn.execute(
            "INSERT INTO rating (ratingid, customerid, productid, loved, ratings, ratingtitle) VALUES (%s, %s, %s, %s, %s, %s)", 
            request.form['rid'], customerid, request.form['pid'], request.form['loved'], request.form['rating'], request.form['text'])

    return redirect('/main')



# Action buying product in main page
@app.route('/buy_product', methods=['POST'])
def buy_product():
    customerid = current_user.uid
    orderdate = datetime.now()
    
    result = g.conn.execute(
        "UPDATE invoice SET quantity=%s, orderid=%s WHERE \
            customerid=%s AND productid=%s AND productname=%s AND orderdate = %s", 
            request.form['quantity'], request.form['orderid'], customerid, 
            request.form['productid'], request.form['productname'], orderdate
            )

    if result.rowcount == 0:
        g.conn.execute(
            "INSERT INTO invoice (orderid, customerid, productid, productname, orderdate, quantity) \
                VALUES (%s, %s, %s, %s, %s, %s)", 
                request.form['orderid'], customerid, request.form['productid'], 
                request.form['productname'], orderdate, request.form['quantity']
                )
        
    return redirect('/main')



# ============================================================
#   CUSTOMER
# ============================================================
@app.route('/customer')
@login_required
def customer():
    # Query: User info
    # cursor = g.conn.execute(
    #     )
    
    # user_info = []
    # user_info = cursor.fetchall()
    
    # cursor.close()
    
    
    # Query: Invoice for this Customer
    cursor = g.conn.execute(
        "SELECT p.productname, c.lastname, c.firstname, c.customerid, c.zipcode, i.orderid, to_char(i.orderdate, 'MM-DD-YYYY'), i.quantity \
            FROM product p, customer c, invoice i, users u \
                WHERE u.uid=i.customerid AND i.customerid = c.customerid AND i.productid = p.productid AND u.uid=%s", 
                current_user.uid)

    purchase_history = []
    purchase_history = cursor.fetchall()

    cursor.close()

  
    # Query this user's reviews for products
    cursor = g.conn.execute(
        "SELECT DISTINCT r.productid, r.ratings, r.ratingtitle, p.productname \
            FROM rating r, users u, product p \
                WHERE r.customerid=u.uid AND p.productid=r.productid AND u.uid=%s", 
                current_user.uid)
  
    user_product_reviews = []
    user_product_reviews = cursor.fetchall()
    cursor.close()

    context=dict(
        purchase_history=purchase_history,
        user_product_reviews=user_product_reviews
        )

    return render_template("customer.html", **context)


# ============================================================
#   Supplier
# ============================================================
@app.route('/supplier')
@login_required
def supplier ():
    # Query: User info
    # cursor = g.conn.execute(
    #     )
    
    # user_info = []
    # user_info = cursor.fetchall()
    
    # cursor.close()
    
    
    # Query: Invoice for this Customer
    cursor = g.conn.execute(
        "SELECT T.productid, S.supplierid, S.suppliername, T.sum_q AS total_quantity \
    FROM (SELECT productID, SUM(quantity) as sum_q \
        FROM invoice GROUP BY productid)T, supplier S \
        WHERE T.productid = S.productid ORDER BY T.sum_q DESC")

    supplier_list= []
    supplier_list = cursor.fetchall()

    cursor.close()

  
   
    context=dict(
        supplier_list=supplier_list     
        )

    return render_template("supplier.html", **context)




# ============================================================
# LOGIN RELATED PAGES
# ============================================================
@login_manager.user_loader
def load_user(username):
    cursor = g.conn.execute("SELECT * FROM Users U WHERE U.username=%s", username)
    data = cursor.fetchone()
    cursor.close()

    if data is None:
        return None

    return User(data[1], data[2], data[3], data[0])

def authenticate_user(user):
    cursor = g.conn.execute("SELECT * FROM Users U WHERE U.username=%s", user.username)
    data = cursor.fetchone()
    cursor.close()

    if data[2] == user.password:
        return True
    return False


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        test_user = User(request.form['username'], request.form['password'])

        if authenticate_user(test_user):
            login_user(test_user)
            return redirect(url_for('main'))
        error = 'Invalid Credentials. Please try again.'

    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    error = None

    if request.method == 'POST':
        try:
            new_user = User(
                request.form['username'],
                request.form['password'],
                request.form['email']
                )

        except ValueError:
            error = "Username or Password is empty"

        if (not is_registered_user(new_user)):
            register_user(new_user)
            login_user(new_user)
            return redirect(url_for('main'))
        error = "Username or email taken."

    return render_template('register.html', error=error)

def register_user(user):
    cursor = g.conn.execute("INSERT INTO Users (username, password, email) VALUES (%s, %s, %s)", 
                            (user.username, user.password, user.email))

    cursor.close()

def is_registered_user(user):
    cursor = g.conn.execute("SELECT * FROM Users U WHERE U.username=%s", (user.username, ))
    data = cursor.fetchone()
    cursor.close()

    if data:
        return True
    return False


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')



# ============================================================
# Run app
# ============================================================
if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)

    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using:

            python server.py

        Show the help text using:

            python server.py --help

        """

        # App configuration for flask-login
        app.secret_key = 'gravano'

        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

    run()
