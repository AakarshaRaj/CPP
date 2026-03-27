from flask import Flask, render_template, request, redirect, session
import boto3
import uuid
from datetime import datetime
from finance_lib import BudgetAnalyzer

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------- AWS CONFIG ----------------
REGION = "us-east-1"
BUCKET = "cpp-s3-demo-bucket"
TOPIC_ARN = "paste-your-topic-arn-here"  # 🔁 replace

# ---------------- AWS CLIENTS ----------------
dynamodb = boto3.resource('dynamodb', region_name=REGION)
users_table = dynamodb.Table('Users')
transactions_table = dynamodb.Table('FinanceApp')

s3 = boto3.client('s3', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)

analyzer = BudgetAnalyzer()

# ---------------- SNS AUTO SUBSCRIBE FUNCTION ----------------
def subscribe_user_if_not_exists(email):
    try:
        print(f"Checking subscription for {email}")

        # Get all subscriptions
        response = sns.list_subscriptions_by_topic(TopicArn=TOPIC_ARN)

        # Check if already subscribed
        for sub in response['Subscriptions']:
            if sub['Endpoint'] == email:
                print("User already subscribed")
                return

        # Subscribe if not exists
        sns.subscribe(
            TopicArn=TOPIC_ARN,
            Protocol='email',
            Endpoint=email
        )

        print(f"📩 Subscription request sent to {email} (confirm required)")

    except Exception as e:
        print("SNS Subscribe Error:", e)


# ---------------- SEND EMAIL ALERT ----------------
def send_email_alert(amount):
    try:
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject="Finance Alert",
            Message=f"⚠️ High expense alert: €{amount}"
        )
        print("SNS alert sent")

    except Exception as e:
        print("SNS Send Error:", e)


# ---------------- HOME ----------------
@app.route('/')
def index():
    return render_template('index.html')


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Save user
            users_table.put_item(
                Item={
                    'email': email,
                    'password': password
                }
            )

            # 🔥 AUTO SUBSCRIBE USER
            subscribe_user_if_not_exists(email)

            return redirect('/login')

        except Exception as e:
            print("Register Error:", e)
            return "Error registering user"

    return render_template('register.html')


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['password']

            res = users_table.get_item(Key={'email': email})
            user = res.get('Item')

            if user and user['password'] == password:
                session['user'] = email
                return redirect('/dashboard')

        except Exception as e:
            print("Login Error:", e)

        return "Invalid credentials"

    return render_template('login.html')


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ---------------- ADD PAGE ----------------
@app.route('/add-page')
def add_page():
    if 'user' not in session:
        return redirect('/login')

    return render_template('add.html')


# ---------------- ADD TRANSACTION ----------------
@app.route('/add', methods=['POST'])
def add():
    if 'user' not in session:
        return redirect('/login')

    try:
        amount = int(request.form['amount'])
        category = request.form.get('category', 'Other')

        file = request.files.get('receipt')
        file_name = None

        # Optional receipt upload
        if file and file.filename != "":
            file_name = str(uuid.uuid4()) + file.filename
            s3.upload_fileobj(file, BUCKET, file_name)

        # Save transaction
        transactions_table.put_item(
            Item={
                'id': str(uuid.uuid4()),
                'user': session['user'],
                'amount': amount,
                'category': category,
                'date': str(datetime.now()),
                'receipt': file_name
            }
        )

        # 🔥 Trigger alert
        if amount > 500:
            send_email_alert(amount)

        return redirect('/dashboard')

    except Exception as e:
        print("Transaction Error:", e)
        return "Error adding transaction"


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    try:
        response = transactions_table.scan()

        data = [
            item for item in response.get('Items', [])
            if item.get('user') == session['user']
        ]

    except Exception as e:
        print("DynamoDB Error:", e)
        data = []

    total = analyzer.calculate_total(data)

    return render_template('dashboard.html', data=data, total=total)


# ---------------- DEBUG ----------------
@app.route('/test')
def test():
    return "App working!"


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)