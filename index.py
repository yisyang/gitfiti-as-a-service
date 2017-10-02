from flask import Flask, abort, json, jsonify, redirect, request, render_template, session, url_for
import hashlib
import random
import requests
from requests.exceptions import HTTPError
import yaml

app = Flask(__name__)

with open('config/config.yml', 'r', encoding='utf-8') as ymlFile:
    config = yaml.load(ymlFile)

app.secret_key = config['flask_session_secret']


@app.route('/', methods=['GET'])
def index():
    """
    Landing Page

    :return: HTML response.
    """

    # Get user information if available.
    user_profile = get_user_profile()

    return render_template(
        'index.html',
        userProfile=user_profile
    ), 200


@app.route('/gitfiti', methods=['GET'])
def gitfiti():
    """
    Main Gitfiti GUI

    :return: HTML response.
    """
    if 'access_token' not in session:
        return redirect(url_for('redirect_to_github_login'))

    # Get user information if available.
    user_profile = get_user_profile()

    return render_template(
        'gitfiti.html',
        userProfile=user_profile
    ), 200


@app.route('/login-github', methods=['GET'])
def redirect_to_github_login():
    """
    Login link on GitHub.

    :return: Redirect to GitHub login page.
    """
    state = get_state_from_seed(get_random_state_seed())

    return redirect(
        'http://github.com/login/oauth/authorize?client_id='
        + config['client_id'] +
        '&redirect_url=http://dev.gitfiti.com/sso-github'
        '&scope=public_repo'
        '&state='
        + state
    )


@app.route('/login-github-success', methods=['GET'])
def login_github_success():
    """
    Callback redirect from GitHub login.

    :return: Redirect to main Gitfiti GUI.
    """
    # Check input state.
    if not verify_state(request.args.get('state', None)):
        return 'Invalid state.'

    access_token = get_access_token_from_github(request.args.get('code'))
    if not access_token:
        return 'Failed to retrieve access token from Github.'

    session['access_token'] = access_token
    return redirect(url_for('gitfiti'))


@app.route('/logout-github', methods=['GET'])
def logout_github():
    del session['access_token']
    del session['user_profile']
    return redirect('https://github.com/settings/connections/applications/a9cf5872fc5369927967')


@app.route('/post-commits-to-github', methods=['POST'])
def post_commits_to_github():
    if not (request.json and 'commits' in request.json):
        return jsonify({
            'message': 'Required parameter "commits" is missing.'
        }), 400
    commits = request.json['commits']

    if True:
        return jsonify({
            'message': 'Sorry, API is not ready yet.'
        }), 400

    return jsonify({
        'message': 'Success!',
        'commits': commits
    }), 200


def call_github_api(method, route, body=''):
    if 'access_token' not in session:
        return redirect(url_for('redirect_to_github_login'))

    # Call github.
    func = getattr(requests, method.lower())
    resp = func('https://api.github.com/' + route,
                data=json.dumps(body),
                verify=True,
                headers={
                    "content-type": "application/json",
                    "accept": "application/json",
                    "Authorization": "Bearer " + session.get('access_token')
                })

    # Decode response.
    content = resp.json()

    # If code is in successful range, we can return it.
    if 200 <= resp.status_code < 400:
        return content

    raise HTTPError('Bad HTTP response.', content, resp)


def get_access_token_from_github(code):
    """
    Exchange input GitHub OAuth code for GitHub access_token.

    :param code: OAuth authorization code.
    :return: User access token.
    """

    body = {
        "client_id": config['client_id'],
        "client_secret": config['client_secret'],
        "code": code,
        "redirect_uri": "http://dev.gitfiti.com/login-github-success"
    }
    resp = requests.post('https://github.com/login/oauth/access_token',
                         data=json.dumps(body),
                         verify=True,
                         headers={
                             "content-type": "application/json",
                             "accept": "application/json"
                         })

    # Verify response.
    if resp.status_code is 200:
        # If request accepted, we can decode it.
        content = resp.json()

        # Grab access token if found.
        if 'access_token' in content:
            return content['access_token']

    # We don't really care about what sort of error happened.
    # Only that we failed to login.
    return None


def get_random_state_seed():
    """
    Generate random state seed.

    :return: String
    """

    # noinspection PyUnusedLocal,SpellCheckingInspection
    return ''.join(random.choice('0123456789abdef') for i in range(10))


def get_state_from_seed(state_seed):
    """
    Compute simple cryptographic state from random state seed.
    Completely stateless but susceptible to replay attacks.

    :param state_seed: Randomly generated 10-character state seed.
    :return: String
    """

    state_peppered = state_seed.encode('utf-8') + config['state_pepper'].encode('utf-8')
    state_hash = hashlib.sha256(state_peppered).hexdigest()

    return state_seed + state_hash


def get_user_profile():
    """
    Get user profile using access token in session.

    :return: User profile as an array, or None.
    """
    # Get user information if available.
    user_profile = None
    if 'access_token' in session:
        if 'user_profile' in session:
            user_profile = session.get('user_profile')
        else:
            try:
                user_profile = call_github_api('GET', 'user')
            except HTTPError:
                return 'Failed to access user details at Github.'
            session['user_profile'] = user_profile
    return user_profile


def verify_state(state_in):
    """
    Verify checksum for state_in to protect against forgery.

    :param state_in: Previously generated state.
    :return Boolean: True if successful, False otherwise.
    """

    if not state_in:
        return False

    # Compute
    state_seed = state_in[:10]
    state = get_state_from_seed(state_seed)

    # Check state against forgery.
    if state != state_in:
        return False

    return True
