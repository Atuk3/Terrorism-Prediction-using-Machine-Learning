# Import necessary libraries
import json
import os
import io
from datetime import date, timedelta, datetime
from flask import Flask,render_template, request, jsonify,flash,url_for,redirect,session,make_response
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import DecimalField, EmailField, IntegerField,  StringField, PasswordField, SubmitField, SelectField, DateField, TextAreaField
from flask_login import UserMixin,login_user,login_required,logout_user,current_user
from werkzeug.utils import secure_filename
from wtforms.validators import InputRequired, DataRequired, EqualTo, Length, ValidationError, NumberRange
from sqlalchemy.sql import func
from flask_bcrypt import Bcrypt
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user,LoginManager
from functools import wraps
from flask import redirect, url_for, flash
from flask import request, render_template, make_response
import pandas as pd
from joblib import load 


# from flask import Flask
# from flask_mail import Mail, Message

# Initialize Flask application
app=Flask(__name__)

# Set Flask application configurations
db=SQLAlchemy()
DB_NAME="database.db"
app.config['SECRET_KEY']='david'
app.config['UPLOAD_FOLDER']='static/files'
app.config['SQLALCHEMY_DATABASE_URI']=f'sqlite:///{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt= Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


 


#----------------------------------------------------------------
#Database Creation
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)






#----------------------------------------------------------------
# FORM CREATION
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), DataRequired() , Length(min=4, max=20)], render_kw= {"placeholder":"Enter Username"})
    password = PasswordField('Password', validators=[InputRequired(), DataRequired(), Length(min=7, max=20)], render_kw= {"placeholder":"Enter Password"})
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), DataRequired(), EqualTo('password'), Length(min=7, max=20)], render_kw= {"placeholder":"Confirm Password"})
    role = SelectField('Role', choices=[('admin', 'Admin'),('officer', 'Police Officer')], validators=[DataRequired()])
    submit = SubmitField('Register')


    def validate_username(self, username):
        existing_user_username = User.query.filter_by(username=username.data).first()

        if existing_user_username:
            raise ValidationError('Username already exists. Please choose a different username.')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), DataRequired() , Length(min=4, max=20)], render_kw= {"placeholder":"Enter Username"})
    password = PasswordField('Password', validators=[InputRequired(), DataRequired(), Length(min=7, max=20)], render_kw= {"placeholder":"Enter Password"})
    submit = SubmitField('Login')




# ----------------------------------------------------------------  

def role_required(allowed_roles):
    """Decorator to restrict access based on roles."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if current_user.is_authenticated and current_user.role in allowed_roles:
                return func(*args, **kwargs)
            flash("You do not have access to this page.", "danger")
            return redirect(url_for('dashboard'))  # Redirect to a safe page
        return wrapper
    return decorator
  
# Define the homepage route
@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])

def home():

   # Render the homepage template for GET requests
    return render_template('index.html')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/register', methods=['GET', 'POST'])

def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(username=form.username.data, password=hashed_password, role=form.role.data)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))
       
    return render_template('login.html', form=form)

from datetime import date
@app.route('/dashboard')
@login_required
def dashboard():

    

    return render_template(
        'dashboard.html'
    )

# Load the trained machine learning model and label encoders using joblib
rf_model = load('terrorism_rfmodel.joblib')  # Update the filename if necessary
label_encoder_state = load('label_encoder_state.joblib')
label_encoder_attack = load('label_encoder_attack.joblib')
@app.route('/machinelearning', methods=['GET', 'POST'])
def machinelearning():
    if request.method == 'POST':
        try:
            # Get user input from form
            year = int(request.form['year'])
            month = int(request.form['month'])
            state = request.form['state']
            attack_type = request.form['attackType']

            # Check if the year is valid (between current year and the next year)
            current_year = datetime.now().year
            if year < current_year or year > current_year + 1:
                flash(f'Error: Year must be the current year or the next year ({current_year} or {current_year + 1}).', 'danger')
                return redirect(url_for('machinelearning'))
             
             # Check if the month is between 1 and 12
            if month < 1 or month > 12:
                flash('Error: Month must be between 1 and 12.', 'danger')
                return redirect(url_for('machinelearning'))
            
            # Check if the inputs are valid
            if state not in label_encoder_state.classes_:
                flash('Error: The selected state is not recognized in the training data.', 'danger')
                return redirect(url_for('machinelearning'))
            
            if attack_type not in label_encoder_attack.classes_:
                flash('Error: The selected attack type is not recognized in the training data.', 'danger')
                return redirect(url_for('machinelearning'))

            # Encode categorical inputs
            encoded_state = label_encoder_state.transform([state])[0]
            encoded_attack_type = label_encoder_attack.transform([attack_type])[0]

            # Create a DataFrame for prediction
            input_data = pd.DataFrame({
                'iyear': [year],
                'imonth': [month],
                'attacktype1_txt_encoded': [encoded_attack_type],
                'provstate_encoded': [encoded_state]
                
            })

            # Make prediction
            probability = rf_model.predict_proba(input_data)[0][1]  # Probability of attack (1)
            prediction = rf_model.predict(input_data)[0]  # Predicted class (1 or 0)

            # Prepare the result message
            if prediction == 1:
                result_message = "Attack is likely to occur."
            else:
                result_message = "No attack is likely to occur."

            return render_template(
                'machinelearning.html',year=year,month=month,state=state,attack_type=attack_type,
                prediction={
                    'message': result_message,
                    'probability': round(probability * 100, 2)
                }
            )
        except Exception as e:
            flash(f"An error occurred: {str(e)}", 'danger')
            return redirect(url_for('machinelearning'))

    return render_template('machinelearning.html')

@app.route('/dataanalysis', methods=['GET', 'POST'])
def dataanalysis():
    try:
        # Load the dataset (replace with the correct path to your dataset)
        dataset_path = "nigeriaglobalterrorismdb.csv"
        df = pd.read_csv(dataset_path)

        # Initialize variables for summary statistics
        total_attacks = len(df)
        most_frequent_attack = df['attacktype1_txt'].mode()[0] if not df.empty else "N/A"
        most_affected_state = df['provstate'].mode()[0] if not df.empty else "N/A"

        # Initialize chart data
        attacks_by_year = df.groupby('iyear').size().reset_index(name='count')
        chart_data = attacks_by_year.to_dict(orient='records')

        # Handle filtering logic for POST requests
        if request.method == 'POST':
            # Get filters from the form
            year = request.form.get('year')
            state = request.form.get('state')
            attack_type = request.form.get('attackType')

            # Apply filters if provided
            if year:
                df = df[df['iyear'] == int(year)]
            if state:
                df = df[df['provstate'] == state]
            if attack_type:
                df = df[df['attacktype1_txt'] == attack_type]

            # Recalculate summary statistics after filtering
            total_attacks = len(df)
            most_frequent_attack = df['attacktype1_txt'].mode()[0] if not df.empty else "N/A"
            most_affected_state = df['provstate'].mode()[0] if not df.empty else "N/A"

            # Update chart data
            attacks_by_year = df.groupby('iyear').size().reset_index(name='count')
            chart_data = attacks_by_year.to_dict(orient='records')

        # Render the Data Analysis page with results
        return render_template(
            'dataanalysis.html',
            total_attacks=total_attacks,
            most_frequent_attack=most_frequent_attack,
            most_affected_state=most_affected_state,
            chart_data=chart_data
        )
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'danger')
        return render_template('dataanalysis.html')



@app.route('/historicalrecords', methods=['GET', 'POST'])
def historicalrecords():
    try:
        # Load dataset
        dataset_path = "nigeriaglobalterrorismdb.csv"
        df = pd.read_csv(dataset_path)

        # Pagination variables
        per_page = 10
        page = request.args.get('page', 1, type=int)
        offset = (page - 1) * per_page
        total_pages = (len(df) + per_page - 1) // per_page

        # Pagination range logic
        max_page_numbers = 10  # Maximum number of pages to display
        start_page = max(1, page - max_page_numbers // 2)
        end_page = min(total_pages, start_page + max_page_numbers - 1)
        if end_page - start_page + 1 < max_page_numbers:
            start_page = max(1, end_page - max_page_numbers + 1)

        # Apply filters
        if request.method == 'POST':
            year = request.form.get('year')
            state = request.form.get('state')
            attack_type = request.form.get('attackType')

            if year:
                df = df[df['iyear'] == int(year)]
            if state:
                df = df[df['provstate'] == state]
            if attack_type:
                df = df[df['attacktype1_txt'] == attack_type]

        # Paginate results
        records = df.iloc[offset:offset + per_page].to_dict(orient='records')

        return render_template(
            'historicalrecords.html',
            records=records,
            pages=range(start_page, end_page + 1),
            current_page=page,
            total_pages=total_pages
        )
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect('/dashboard')


@app.route('/historicalrecords/export')
def export_csv():
    try:
        dataset_path = "nigeriaglobalterrorismdb.csv"
        df = pd.read_csv(dataset_path)
        response = make_response(df.to_csv(index=False))
        response.headers["Content-Disposition"] = "attachment; filename=historical_records.csv"
        response.headers["Content-Type"] = "text/csv"
        return response
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect('/historicalrecords')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('Created User Database!')
    app.run(debug=True)