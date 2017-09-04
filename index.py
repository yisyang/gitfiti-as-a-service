from flask import Flask
from flask import abort, redirect, request, render_template, session, url_for
import hashlib
import json
import random
import requests
import yaml

app = Flask(__name__)

with open('config/config.yml', 'r', encoding='utf-8') as ymlFile:
    config = yaml.load(ymlFile)

app.secret_key = config['flask_session_secret']


@app.route('/abort')
def abort():
    abort(501)


@app.route('/')
def main():
    return render_template(
        'main.html',
        something="everything"
    ), 200


@app.route('/gitfiti')
def gitfiti():
    if 'access_token' not in session:
        return redirect(url_for('redirect_to_github_login'))

    return render_template(
        'gitfiti.html'
    ), 200


@app.route('/login-github')
def redirect_to_github_login():
    state = get_state_from_seed(get_random_state_seed())

    return redirect(
        'http://github.com/login/oauth/authorize?client_id='
        + config['client_id'] +
        '&redirect_url=http://dev.gitfiti.com/sso-github'
        '&scope=public_repo'
        '&state='
        + state
    )


@app.route('/login-github-success')
def login_github_success():
    # Check input state.
    if not verify_state(request.args.get('state', None)):
        return 'Invalid state.'

    access_token = get_access_token_from_github(request.args.get('code'))
    if not access_token:
        return 'Failed to retrieve access token from Github.'

    session['access_token'] = access_token
    return redirect(url_for('gitfiti'))


@app.route('/login-github-with-delete')
def redirect_to_github_login_with_delete():
    state = get_state_from_seed(get_random_state_seed())

    return redirect(
        'http://github.com/login/oauth/authorize?client_id=a9cf5872fc5369927967'
        '&redirect_url=http://dev.gitfiti.com/sso-github'
        '&scope=public_repo,delete_repo'
        '&state='
        + state
    )


@app.route('/logout-github')
def logout_github():
    return redirect('https://github.com/settings/connections/applications/a9cf5872fc5369927967')


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


def verify_state(state_in):
    """
    Verify checksum for state_in to protect against forgery.

    :param state_in: Previously generated state.
    :return: Boolean True if successful, False otherwise.
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
