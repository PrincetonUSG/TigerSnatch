# ----------------------------------------------------------------------
# api.py
# Defines endpoints for TigerSnatch app.
# ----------------------------------------------------------------------

from flask import Flask
from flask import render_template, make_response, request, redirect, url_for, jsonify
from database import Database
from CASClient import CASClient
from config import APP_SECRET_KEY
from waitlist import Waitlist
from app_helper import do_search, pull_course

app = Flask(__name__, template_folder='./templates')
app.secret_key = APP_SECRET_KEY
_CAS = CASClient()


@app.errorhandler(Exception)
def handle_exception(e):
    print(e)
    return render_template('error.html')


# private method that redirects to landinage page
# if user is not logged in with CAS
# or if user is logged in with CAS, but doesn't have entry in DB
def redirect_landing():
    return not _CAS.is_logged_in() or not Database().is_user_created(_CAS.authenticate())


@app.route('/', methods=['GET'])
def index():
    if redirect_landing():
        return redirect(url_for('landing'))
    return redirect(url_for('dashboard'))


@app.route('/landing', methods=['GET', 'POST'])
def landing():
    html = render_template('landing.html')
    return make_response(html)


@app.route('/login', methods=['GET'])
def login():
    _db = Database()
    netid = _CAS.authenticate()
    if not _db.is_user_created(netid):
        _db.create_user(netid)

    print(f'user {netid} logged in')

    return redirect(url_for('dashboard'))


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if redirect_landing():
        return redirect(url_for('landing'))

    _db = Database()
    netid = _CAS.authenticate()
    print(f'user {netid} used dashboard')

    data = _db.get_dashboard_data(netid)
    email = _db.get_user(netid)['email']

    query = request.args.get('query')
    new_email = request.form.get('new_email')

    if query is None:
        query = ""
    search_res = do_search(query)

    if new_email is not None:
        _db.update_user(netid, new_email.strip())
        return redirect(url_for('dashboard'))

    html = render_template('base.html',
                           isDashboard=True,
                           search_res=search_res,
                           last_query=query,
                           username=netid.rstrip(),
                           data=data,
                           email=email,
                           dashboard=True)

    return make_response(html)


@app.route('/about', methods=['GET'])
def about():
    if redirect_landing():
        html = render_template('about.html', loggedin=False)
        return make_response(html)

    html = render_template('base.html', loggedin=True)
    return make_response(html)


@app.route('/searchresults', methods=['POST'])
@app.route('/searchresults/<query>', methods=['POST'])
def get_search_results(query=''):
    res = do_search(query)
    html = render_template('search/search_results.html',
                           last_query=query,
                           search_res=res)
    return make_response(html)


@app.route('/courseinfo/<courseid>', methods=['POST'])
def get_course_info(courseid):
    netid = _CAS.authenticate()
    _db = Database()

    course_details, classes_list = pull_course(courseid)
    curr_waitlists = _db.get_user(netid)['waitlists']
    html = render_template('course/course.html',
                           courseid=courseid,
                           course_details=course_details,
                           classes_list=classes_list,
                           curr_waitlists=curr_waitlists)
    return make_response(html)


@app.route('/course', methods=['GET'])
def get_course():
    if not _CAS.is_logged_in():
        return redirect(url_for('landing'))

    netid = _CAS.authenticate()
    _db = Database()

    courseid = request.args.get('courseid')
    query = request.args.get('query')

    print(f'user {netid} accessed courseid {courseid}')

    if query is None:
        query = ""
    search_res = do_search(query)

    course_details, classes_list = pull_course(courseid)
    curr_waitlists = _db.get_user(netid)['waitlists']

    # change to check if updateSearch == 'false'
    # if updateSearch is None:
    html = render_template('base.html',
                           isDashboard=False,
                           netid=netid,
                           courseid=courseid,
                           course_details=course_details,
                           classes_list=classes_list,
                           curr_waitlists=curr_waitlists,
                           search_res=search_res,
                           last_query=query)

    return make_response(html)


@app.route('/logout', methods=['GET'])
def logout():
    _CAS.logout()
    return redirect(url_for('landing'))


@app.route('/add_to_waitlist/<classid>', methods=['POST'])
def add_to_waitlist(classid):
    netid = _CAS.authenticate()
    waitlist = Waitlist(netid)
    return jsonify({"isSuccess": waitlist.add_to_waitlist(classid)})


@app.route('/remove_from_waitlist/<classid>', methods=['POST'])
def remove_from_waitlist(classid):
    netid = _CAS.authenticate()
    waitlist = Waitlist(netid)
    return jsonify({"isSuccess": waitlist.remove_from_waitlist(classid)})
