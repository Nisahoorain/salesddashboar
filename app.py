from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from flask import send_file
from collections import defaultdict
import os
import io
from datetime import datetime, timedelta, date


app = Flask(__name__)
app.secret_key = "nisa123??"  # Necessary for session management


def create_connection(host_name, user_name, user_password, db_name):
    connection = None
    try:
        connection = mysql.connector.connect(
            host=host_name, user=user_name, passwd=user_password, database=db_name
        )
        print("Connection to MySQL DB successful")
    except Error as e:
        print(f"The error '{e}' occurred")
    return connection


def verify_user(connection, user, password):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM users WHERE user = %s AND password = %s", (user, password)
        )
        user = cursor.fetchone()
        return user
    except Error as e:
        print(f"The error '{e}' occurred")
        return None


def fetch_all_users(connection):
    users = []
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, user, role, created_at, status FROM users")
        users = cursor.fetchall()
    except Error as e:
        print(f"The error '{e}' occurred")
    finally:
        cursor.close()
    return users


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("login.html", message=session.pop("message", None))

@app.route("/login", methods=["POST", "GET"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        user = request.form["user"]
        password = request.form["password"]

        connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")

        if connection:
            user_data = verify_user(connection, user, password)
            if user_data:
                if user_data["status"] == "active":
                    session["user_id"] = user_data["id"]
                    session["user_name"] = user_data["user"]
                    session["role"] = user_data["role"]

                    # Redirect based on user role
                    if session["role"] == "Scrapper":
                        return redirect(url_for("file"))
                    elif session["role"] == "Sale Agent":
                        return redirect(url_for("number"))
                    elif session["role"] == "Admin":
                        return redirect(url_for("home"))
                elif user_data["status"] == "archive":
                    session["message"] = "Your account is archived. Please contact support."
                else:
                    session["message"] = "Your account is currently inactive. Please contact support."

                return redirect(url_for("index"))
            else:
                session["message"] = "Invalid user or password."
                return redirect(url_for("index"))
        else:
            session["message"] = "Failed to connect to database."
            return redirect(url_for("index"))

    return render_template("login.html")

@app.route("/archive_user/<int:user_id>")
def archive_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("index"))
    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    if connection:
        if update_user_status(connection, user_id, "archive"):
            session["message"] = "User archived successfully."
        else:
            session["message"] = "Failed to archive user."

        return redirect(url_for("users"))
    else:
        session["message"] = "Failed to connect to database."
        return redirect(url_for("index"))

@app.route("/unarchive_user/<int:user_id>")
def unarchive_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("index"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    if connection:
        if update_user_status(connection, user_id, "active"):
            session["message"] = "User unarchived successfully."
        else:
            session["message"] = "Failed to unarchive user."

        return redirect(url_for("users"))
    else:
        session["message"] = "Failed to connect to database."
        return redirect(url_for("index"))

def update_user_status(connection, user_id, status):
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE users SET status = %s WHERE id = %s", (status, user_id))
        connection.commit()
        return True
    except Exception as e:
        print(f"Error updating user status: {e}")
        connection.rollback()
        return False
    finally:
        cursor.close()
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("role", None)
    session["message"] = "You have been logged out."
    return redirect(url_for("index"))

@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect(url_for("index"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Existing counts
            cursor.execute("SELECT COUNT(*) AS scrapper_count FROM users WHERE role = 'Scrapper'")
            scrapper_count = cursor.fetchone()["scrapper_count"]

            cursor.execute("SELECT COUNT(*) AS sales_agent_count FROM users WHERE role = 'Sale Agent'")
            sales_agent_count = cursor.fetchone()["sales_agent_count"]

            cursor.execute("""
                SELECT COUNT(*) AS monthly_sales_count
                FROM orders
                WHERE approve = 'Approved' AND MONTH(time) = MONTH(CURDATE()) AND YEAR(time) = YEAR(CURDATE())
            """)
            monthly_sales_count = cursor.fetchone()["monthly_sales_count"]

            cursor.execute("""
                SELECT COUNT(*) AS monthly_phone_numbers_count
                FROM unique_numbers
                WHERE MONTH(upload_time) = MONTH(CURDATE()) AND YEAR(upload_time) = YEAR(CURDATE())
            """)
            monthly_phone_numbers_count = cursor.fetchone()["monthly_phone_numbers_count"]

            # New query to fetch approved sales grouped by agent name
            cursor.execute("""
                SELECT agent_name, COUNT(*) AS sales_count
                FROM orders
                WHERE approve = 'Approved'
                GROUP BY agent_name
            """)
            sales_by_agent = cursor.fetchall()

            # New query to fetch monthly sales for the current year
            cursor.execute("""
                SELECT MONTH(time) AS month, COUNT(*) AS sales_count
                FROM orders
                WHERE approve = 'Approved' AND YEAR(time) = YEAR(CURDATE())
                GROUP BY MONTH(time)
                ORDER BY MONTH(time)
            """)
            monthly_sales = cursor.fetchall()

            # New query to fetch monthly phone number counts for the current year
            cursor.execute("""
                SELECT MONTH(upload_time) AS month, COUNT(*) AS phone_number_count
                FROM unique_numbers
                WHERE YEAR(upload_time) = YEAR(CURDATE())
                GROUP BY MONTH(upload_time)
                ORDER BY MONTH(upload_time)
            """)
            monthly_phone_numbers = cursor.fetchall()

        except Error as e:
            session["message"] = f"Failed to fetch data: {e}"
            return redirect(url_for("index"))
        finally:
            cursor.close()

        return render_template(
            "home.html",
            user=session["user_name"],
            message=session.pop("message", None),
            scrapper_count=scrapper_count,
            sales_agent_count=sales_agent_count,
            monthly_sales_count=monthly_sales_count,
            monthly_phone_numbers_count=monthly_phone_numbers_count,
            sales_by_agent=sales_by_agent,  # Pass the new data to the template
            monthly_sales=monthly_sales,  # Pass the new data to the template
            monthly_phone_numbers=monthly_phone_numbers  # Pass the new data to the template
        )
    else:
        session["message"] = "Failed to connect to database."
        return redirect(url_for("index"))

@app.route("/file", methods=['GET', 'POST'])
def file():
    if "user_id" not in session:
        return redirect(url_for("index"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Get filter values from the request
            filter_option = request.form.get('filter_option', 'today')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')

            # Determine the date range based on the filter option
            if filter_option == 'today':
                start_date = datetime.now().strftime('%Y-%m-%d')
                end_date = start_date
            elif filter_option == 'this_month':
                start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
                end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            elif filter_option == 'custom':
                # Use the provided start_date and end_date
                pass
            else:
                start_date = datetime.now().strftime('%Y-%m-%d')
                end_date = start_date

            # Check if the user is admin
            is_admin = session["role"] == "Admin"

            # Fetch files data based on the date range
            query = """
                SELECT id, filename, username, skip_count, add_count, add_percentage, upload_time
                FROM uploaded_files
                WHERE DATE(upload_time) BETWEEN %s AND %s
                {}
                ORDER BY upload_time DESC
            """.format("" if is_admin else "AND username = %s")
            
            params = (start_date, end_date)
            if not is_admin:
                params += (session["user_name"],)

            cursor.execute(query, params)
            files_data = cursor.fetchall()

            # Fetch settings data
            cursor.execute("SELECT * FROM settings WHERE id = 1")
            settings = cursor.fetchone()

            ratio_per_request = settings["ratio_per_request"] if settings else 0
            time_interval = settings["time_interval"] if settings else 0

            # Calculate remaining numbers count
            cursor.execute("SELECT COUNT(*) AS remaining_count FROM unique_numbers WHERE assigned = FALSE")
            remaining_count = cursor.fetchone()["remaining_count"]

            # Calculate overall totals
            total_skip_count = sum(file_data["skip_count"] for file_data in files_data)
            total_add_count = sum(file_data["add_count"] for file_data in files_data)
            total_add_percentage = (total_add_count / total_skip_count) * 100 if total_skip_count > 0 else 0

            # Calculate individual totals
            user_totals = defaultdict(lambda: {"username": None, "total_skip_count": 0, "total_add_count": 0, "total_add_percentage": 0})

            for file_data in files_data:
                username = file_data["username"]
                user_totals[username]["username"] = username
                user_totals[username]["total_skip_count"] += file_data["skip_count"]
                user_totals[username]["total_add_count"] += file_data["add_count"]
                user_totals[username]["total_add_percentage"] = (
                    (user_totals[username]["total_add_count"] / user_totals[username]["total_skip_count"]) * 100
                    if user_totals[username]["total_skip_count"] > 0 else 0
                )

            individual_totals = list(user_totals.values())

            return render_template(
                "files.html",
                files_data=files_data,
                total_skip_count=total_skip_count,
                total_add_count=total_add_count,
                total_add_percentage=total_add_percentage,
                individual_totals=individual_totals,
                remaining_numbers=remaining_count,
                ratio_per_request=ratio_per_request,
                time_interval=time_interval,
                message=session.pop("message", None)
            )

        except Error as e:
            session["message"] = f"Failed to fetch data: {e}"
            return redirect(url_for("index"))
        finally:
            cursor.close()
    else:
        session["message"] = "Failed to connect to database."
        return redirect(url_for("index"))

def fetch_settings(connection):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM settings WHERE id = 1"
        )  # Assuming settings are stored in a table named 'settings'
        settings = cursor.fetchone()
        return settings
    except Error as e:
        raise e
    finally:
        cursor.close()
@app.route("/update_settings", methods=["POST"])
def update_settings():
    if "user_id" not in session:
        return redirect(url_for("index"))

    ratio_per_request = request.form.get("ratio_per_request")
    time_interval = request.form.get("time_interval")

    print("Received ratio_per_request:", ratio_per_request)
    print("Received time_interval:", time_interval)

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")

    if connection:
        try:
            with connection.cursor() as cursor:
                # Check if there are any rows in the settings table
                cursor.execute("SELECT COUNT(*) FROM settings")
                result = cursor.fetchone()
                row_count = result[0]

                if row_count == 0:
                    # If table is empty, insert a new row
                    cursor.execute(
                        "INSERT INTO settings (ratio_per_request, time_interval) VALUES (%s, %s)",
                        (ratio_per_request, time_interval),
                    )
                    print("Settings inserted successfully!")
                else:
                    # If table is not empty, update the existing row
                    cursor.execute(
                        "UPDATE settings SET ratio_per_request = %s, time_interval = %s WHERE id = 1",
                        (ratio_per_request, time_interval),
                    )
                    print("Settings updated successfully!")

                connection.commit()
                session["message"] = "Settings updated successfully!"
        except Error as e:
            connection.rollback()
            session["message"] = f"Failed to update settings: {e}"
            print(f"Failed to update settings: {e}")
        finally:
            connection.close()
    else:
        session["message"] = "Failed to connect to database."
        print("Failed to connect to database.")

    return redirect(url_for("file"))


@app.route("/users")
def users():
    if "user_id" not in session:
        return redirect(url_for("index"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    if connection:
        users_data = fetch_all_users(connection)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS admin_count FROM users WHERE role = 'Admin'")
        admin_count = cursor.fetchone()["admin_count"]
        cursor.close()
        return render_template(
            "users.html", users=users_data, admin_count=admin_count, message=session.pop("message", None)
        )
    else:
        session["message"] = "Failed to connect to database."
        return redirect(url_for("index"))


@app.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("index"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    
    if request.method == "POST":
        username = request.form["username"]
        role = request.form["role"]
        new_password = request.form.get("new_password")
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS admin_count FROM users WHERE role = 'Admin'")
        admin_count = cursor.fetchone()["admin_count"]

        # Check if changing the role to 'Admin' is allowed
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        current_role = cursor.fetchone()["role"]

        if role == "Admin" and admin_count >= 5 and current_role != "Admin":
            session["message"] = "Cannot change role to Admin. Maximum of 5 admins allowed."
        else:
            try:
                if new_password:
                    cursor.execute(
                        "UPDATE users SET user = %s, role = %s, password = %s WHERE id = %s",
                        (username, role, new_password, user_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET user = %s, role = %s WHERE id = %s",
                        (username, role, user_id),
                    )
                connection.commit()
                session["message"] = "User updated successfully!"
            except Error as e:
                session["message"] = f"Failed to update user: {e}"
            finally:
                cursor.close()
            return redirect(url_for("users"))
    
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()

    return render_template("edit_user.html", user=user, message=session.pop("message", None))


@app.route("/create_user", methods=["POST"])
def create_user():
    if "user_id" not in session:
        return redirect(url_for("index"))

    username = request.form["username"]
    role = request.form["role"]
    password = request.form["newpassword"]
    re_password = request.form["renewpassword"]

    if password != re_password:
        session["message"] = "Passwords do not match!"
        return redirect(url_for("users"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")

    if connection:
        cursor = connection.cursor()
        try:
            # Check if the username already exists
            cursor.execute("SELECT COUNT(*) FROM users WHERE user = %s", (username,))
            result = cursor.fetchone()
            if result[0] > 0:
                session["message"] = "Username already exists!"
            else:
                # Add the 'created_at' field with the current timestamp
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO users (user, role, password, created_at) VALUES (%s, %s, %s, %s)",
                    (username, role, password, current_time),
                )
                connection.commit()
                session["message"] = "User created successfully!"
        except Error as e:
            session["message"] = f"Failed to create user: {e}"
        finally:
            cursor.close()
    else:
        session["message"] = "Failed to connect to database."

    return redirect(url_for("users"))

@app.route("/upload_file", methods=["POST"])
def upload_file():
    if "user_name" not in session:
        return redirect(url_for("index"))

    file = request.files["file"]

    if file.filename == "":
        session["message"] = "No file selected for uploading."
        return redirect(url_for("file"))

    try:
        connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
        if connection:
            handle_uploaded_file(file, file.filename, session["user_name"], connection)
            session["message"] = "File uploaded successfully."
        else:
            session["message"] = "Failed to connect to database."
    except Exception as e:
        session["message"] = f"Error uploading file: {str(e)}"

    return redirect(url_for("file"))


def handle_uploaded_file(file, file_name, username, connection):
    cursor = connection.cursor()
    try:
        # Save uploaded file details to 'uploaded_files' table
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_content, skip_count, add_count, total_count, details_list = (
            process_file_data(file, connection)
        )
        add_percentage = (add_count / total_count) * 100 if total_count > 0 else 0
        cursor.execute(
            "INSERT INTO uploaded_files (username, filename, file_content, upload_time, skip_count, add_count, add_percentage) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                username,
                file_name,
                file_content,
                current_time,
                skip_count,
                add_count,
                add_percentage,
            ),
        )
        connection.commit()

        # Save unique phone numbers to 'unique_numbers' table
        save_unique_numbers(file_content, connection, details_list, current_time)
    except Error as e:
        connection.rollback()
        raise e
    finally:
        cursor.close()

def process_file_data(file, connection):
    file_content = ""
    add_count = 0
    total_count = 0
    details_list = []

    for line in file:
        data = line.decode().strip().split("\t")  # Assuming tab-separated data
        if len(data) > 0:
            total_count += 1
            phone_number = data[0]
            details = "\t".join(data[1:])  # Combine the rest of the columns as details
            details_list.append((phone_number, details))
            # Check if phone_number already exists in 'unique_numbers' table
            number_exists = check_number_exists(phone_number, connection)
            if not number_exists:
                file_content += line.decode().strip() + "\n"
                add_count += 1

    skip_count = total_count  # Set skip_count to total_count
    return file_content, skip_count, add_count, total_count, details_list


def check_number_exists(phone_number, connection):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM unique_numbers WHERE phone_number = %s", (phone_number,)
    )
    result = cursor.fetchone()[0]
    cursor.close()
    return result > 0


def save_unique_numbers(file_content, connection, details_list, upload_time):
    cursor = connection.cursor()
    try:
        for phone_number, details in details_list:
            cursor.execute(
                "INSERT IGNORE INTO unique_numbers (phone_number, details, upload_time) VALUES (%s, %s, %s)",
                (phone_number, details, upload_time),
            )
        connection.commit()
    except Error as e:
        connection.rollback()
        raise e
    finally:
        cursor.close()

@app.route("/view_file/<int:file_id>")
def view_file(file_id):
    if "user_id" not in session:
        return redirect(url_for("index"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Fetch file data by file_id
            cursor.execute(
                "SELECT file_content FROM uploaded_files WHERE id = %s", (file_id,)
            )
            file_data = cursor.fetchone()

            if file_data:
                # Render a new template to display file content
                return render_template(
                    "view.html", file_content=file_data["file_content"]
                )
            else:
                session["message"] = "File not found."
                return redirect(url_for("file"))
        except Error as e:
            session["message"] = f"Failed to fetch file data: {e}"
            return redirect(url_for("file"))
        finally:
            cursor.close()
    else:
        session["message"] = "Failed to connect to database."
        return redirect(url_for("index"))


@app.route("/add_order", methods=["POST"])
def add_order():
    if "user_id" not in session:
        return redirect(url_for("index"))

    order_data = {
        "order_id": request.form["orderId"],
        "time": request.form["time"],  # This will be in the format 'YYYY-MM-DDTHH:MM'
        "status": request.form["orderStatus"],
        "customer_name": request.form["customerName"],
        "customer_phone": request.form["customerPhone"],
        "customer_vin": request.form["customerVIN"],
        "package": request.form["package"],
        "agent_name": request.form["agentName"],
        "approve": request.form["approve"],
    }

    # Parse the datetime-local string to a datetime object
    order_time = datetime.strptime(order_data["time"], "%Y-%m-%dT%H:%M")

    # Get the uploaded screenshot file
    screenshot_file = request.files["screenshot"]

    # Convert the screenshot file to binary data
    screenshot_blob = screenshot_file.read()

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")

    if connection:
        cursor = connection.cursor()

        # Check if order with the same order_id already exists
        cursor.execute(
            "SELECT COUNT(*) FROM orders WHERE order_id = %s", (order_data["order_id"],)
        )
        order_exists = cursor.fetchone()[0]

        if order_exists:
            session["message"] = "Order with this ID already exists."
            return redirect(url_for("order"))

        # Insert the new order if it does not already exist
        cursor.execute(
            "INSERT INTO orders (order_id, time, status, customer_name, customer_phone, customer_vin, package, agent_name, approve, screenshot) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                order_data["order_id"],
                order_time,
                order_data["status"],
                order_data["customer_name"],
                order_data["customer_phone"],
                order_data["customer_vin"],
                order_data["package"],
                order_data["agent_name"],
                order_data["approve"],
                screenshot_blob,
            ),
        )
        connection.commit()
        cursor.close()

        session["message"] = "Order added successfully."

    return redirect(url_for("order"))

@app.route("/search", methods=['POST'])
def search():
    search_query = request.form['search_query'].strip()  # Strip leading/trailing whitespaces

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    if connection:
        try:
            with connection.cursor(dictionary=True) as cursor:
                # Debug statement to print the search query
                print(f"Search Query: {search_query}")

                # Search for the phone number in assigned_numbers table
                cursor.execute("SELECT * FROM assigned_numbers WHERE phone_number = %s", (search_query,))
                assigned_numbers_data = cursor.fetchone()

                if assigned_numbers_data:
                    user_id = assigned_numbers_data['user_id']

                    # Fetch user details from users table
                    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                    user_data = cursor.fetchone()

                    # Debug statements to print the fetched data
                    print(f"Assigned Numbers Data: {assigned_numbers_data}")
                    print(f"User Data: {user_data}")

                    # Return JSON response
                    return jsonify({
                        'assigned_numbers': assigned_numbers_data,
                        'user': user_data
                    })
                else:
                    # No results found for the search query
                    return jsonify({
                        'message': 'No results found for the search query.'
                    })
        except Exception as e:
            print(f"Error fetching data: {e}")
        finally:
            connection.close()

    # If no results found or error occurred, return an error message
    return jsonify({
        'error': 'Failed to retrieve data.'
    })

@app.route("/order", methods=['GET', 'POST'])
def order():
    if "user_id" not in session:
        return redirect(url_for("index"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    orders = []
    sales_agents = []
    message = session.pop("message", None)

    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get filter options from form
        filter_option = request.form.get('filter_option', 'today')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        # Default to today if no filter option is selected
        if filter_option == 'today':
            today = date.today()
            start_date = today
            end_date = today
        elif filter_option == 'this_month':
            today = date.today()
            start_date = today.replace(day=1)
            end_date = today
        elif filter_option == 'custom' and start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            # Default to today if no valid filter option is provided
            today = date.today()
            start_date = today
            end_date = today
        
        # Fetch orders based on the filter options
        query = "SELECT * FROM orders WHERE DATE(time) BETWEEN %s AND %s"
        cursor.execute(query, (start_date, end_date))
        orders = cursor.fetchall()

        # Fetch users with the role 'Sales Agent'
        cursor.execute("SELECT id, user FROM users WHERE role = 'Sale Agent'")
        sales_agents = cursor.fetchall()

        cursor.close()

    return render_template(
        "order.html",
        orders=orders,
        sales_agents=sales_agents,
        user=session["user_name"],
        message=message
    )


@app.route("/screenshot/<int:order_id>")
def screenshot(order_id):
    if "user_id" not in session:
        return redirect(url_for("index"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")

    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT screenshot FROM orders WHERE id = %s", (order_id,))
        screenshot_data = cursor.fetchone()
        cursor.close()

        if screenshot_data and screenshot_data[0]:
            return send_file(io.BytesIO(screenshot_data[0]), mimetype="image/png")

    return "Screenshot not found", 404


@app.route("/update_approve_status/<int:order_id>", methods=["POST"])
def update_approve_status(order_id):
    if "user_id" not in session:
        return redirect(url_for("index"))

    approve_status = request.form["approve_status"]

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")

    if connection:
        cursor = connection.cursor()
        query = "UPDATE orders SET approve = %s WHERE id = %s"
        cursor.execute(query, (approve_status, order_id))
        connection.commit()
        cursor.close()

    return redirect(url_for("order"))


@app.route("/get_number", methods=["POST"])
def get_number():
    if "user_id" not in session:
        return redirect(url_for("index"))

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")

    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Fetch settings
            settings = fetch_settings(connection)
            if not settings:
                session["message"] = "Failed to fetch settings."
                return redirect(url_for("number"))

            ratio_per_request = settings["ratio_per_request"]
            time_interval = settings["time_interval"]

            # Check the last assigned number time for the user
            cursor.execute(
                "SELECT MAX(assigned_at) AS last_assigned_time FROM assigned_numbers WHERE user_id = %s",
                (session["user_id"],)
            )
            last_assigned_time = cursor.fetchone()["last_assigned_time"]

            if last_assigned_time:
                time_diff = (datetime.now() - last_assigned_time).total_seconds()
                if time_diff < time_interval:
                    session["message"] = f"You must wait {int(time_interval - time_diff)} more seconds before requesting new numbers."
                    return redirect(url_for("number"))

            # Fetch numbers based on ratio_per_request
            cursor.execute(
                "SELECT phone_number, details FROM unique_numbers WHERE assigned = FALSE LIMIT %s",
                (ratio_per_request,)
            )
            numbers = cursor.fetchall()

            if numbers:
                # Assign numbers to the current user
                assigned_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for number in numbers:
                    cursor.execute(
                        "INSERT INTO assigned_numbers (user_id, phone_number, details, assigned_at) VALUES (%s, %s, %s, %s)",
                        (
                            session["user_id"],
                            number["phone_number"],
                            number["details"],
                            assigned_time,
                        ),
                    )
                    # Update the assigned status in unique_numbers table
                    cursor.execute(
                        "UPDATE unique_numbers SET assigned = TRUE WHERE phone_number = %s",
                        (number["phone_number"],),
                    )

                connection.commit()
                session["message"] = f"{len(numbers)} phone number(s) have been assigned to you."
            else:
                session["message"] = "No phone numbers available to assign."
        except Error as e:
            session["message"] = f"Failed to assign numbers: {e}"
        finally:
            cursor.close()
    else:
        session["message"] = "Failed to connect to database."

    return redirect(url_for("number"))

@app.route("/number", methods=["GET", "POST"])
def number():
    if "user_id" not in session:
        return redirect(url_for("index"))

    filter_option = request.form.get("filter_option", "today")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")

    connection = create_connection("157.173.210.232", "billuphpmyadmin", "Billuphpmyadmin@3000", "billubaddshah_adminpaneldb")
    numbers = []
    approved_orders = []
    user_requests = []

    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Define date filter conditions
        date_condition = "DATE(assigned_at) = CURDATE()"
        if filter_option == "this_month":
            date_condition = "MONTH(assigned_at) = MONTH(CURDATE()) AND YEAR(assigned_at) = YEAR(CURDATE())"
        elif filter_option == "custom" and start_date and end_date:
            date_condition = f"DATE(assigned_at) BETWEEN '{start_date}' AND '{end_date}'"

        # Fetch assigned numbers based on user role
        if session["role"] == "Admin":
            cursor.execute(f"""
                SELECT an.phone_number, an.details, an.assigned_at, u.user AS assigned_to
                FROM assigned_numbers an
                JOIN users u ON an.user_id = u.id
                WHERE {date_condition}
                ORDER BY an.assigned_at DESC
            """)
        else:
            cursor.execute(f"""
                SELECT phone_number, details, assigned_at
                FROM assigned_numbers
                WHERE user_id = %s AND {date_condition}
                ORDER BY assigned_at DESC
            """, (session["user_id"],))
        numbers = cursor.fetchall()

        # Define date filter conditions for orders
        date_condition = "DATE(time) = CURDATE()"
        if filter_option == "this_month":
            date_condition = "MONTH(time) = MONTH(CURDATE()) AND YEAR(time) = YEAR(CURDATE())"
        elif filter_option == "custom" and start_date and end_date:
            date_condition = f"DATE(time) BETWEEN '{start_date}' AND '{end_date}'"

        # Fetch approved orders based on the user's role
        if session["role"] == "Admin":
            cursor.execute(f"""
                SELECT order_id, customer_phone, package, agent_name
                FROM orders
                WHERE approve = 'Approved' AND {date_condition}
                ORDER BY time DESC
            """)
        elif session["role"] == "Sale Agent":
            cursor.execute(f"""
                SELECT order_id, customer_phone, package, agent_name
                FROM orders
                WHERE approve = 'Approved' AND agent_name = %s AND {date_condition}
                ORDER BY time DESC
            """, (session["user_name"],))
        approved_orders = cursor.fetchall()

        # Define date filter conditions for user requests
        date_condition = "DATE(assigned_at) = CURDATE()"
        if filter_option == "this_month":
            date_condition = "MONTH(assigned_at) = MONTH(CURDATE()) AND YEAR(assigned_at) = YEAR(CURDATE())"
        elif filter_option == "custom" and start_date and end_date:
            date_condition = f"DATE(assigned_at) BETWEEN '{start_date}' AND '{end_date}'"

        # Fetch all 'Sale Agent' users and their request counts
        cursor.execute(f"""
            SELECT u.user, COALESCE(COUNT(an.phone_number), 0) AS requests, MAX(an.assigned_at) AS last_request_time
            FROM users u
            LEFT JOIN assigned_numbers an ON u.id = an.user_id AND {date_condition}
            WHERE u.role = 'Sale Agent'
            GROUP BY u.user
            ORDER BY requests DESC, last_request_time DESC
        """)
        user_requests = cursor.fetchall()

        cursor.close()

    message = session.pop("message", None)
    return render_template("number.html", numbers=numbers, approved_orders=approved_orders, user_requests=user_requests, message=message)

if __name__ == "__main__":
    app.run(debug=True)
