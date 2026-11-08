from app.models import Item, User

TEST_PASSWORD = 'posts test password'

## HELPER FUNCTIONS
# -----------------

def _create_user(test_db, email):
    """Create a user in the database"""

    user = User(email=email)
    user.set_password(TEST_PASSWORD)

    test_db.session.add(user)
    test_db.session.commit()

    return user.id

def _create_item(test_db, user_id, title='Backpack', description='Blue backpack',
                 category='bags', listing_type='lost', general_location='Library'):
    """Create an item in the database"""

    item = Item(user_id=user_id, title=title, description=description,
                category=category, listing_type=listing_type,
                general_location=general_location)

    test_db.session.add(item)
    test_db.session.commit()

    return item.id

def _login(client, email):
    """Log in a user"""

    response = client.post('/auth/login', data={
        'email': email,
        'password': TEST_PASSWORD
    })

    assert response.status_code == 302

def _valid_post_data():
    """Return a valid example of post data"""

    return {
        'title': 'Lost wallet',
        'description': 'Black leather wallet',
        'category': 'Accessories',
        'listing_type': 'lost',
        'general_location': 'Cafeteria'
    }

## GET POST TESTS
# -----------------

def test_get_posts_empty_list(client):
    """Test get_posts() with an empty database"""
    response = client.get('/posts/')

    assert response.status_code == 200
    assert response.get_json() == {'posts': []}

def test_gets_posts_with_filters(client, test_db):
    user_id = _create_user(test_db, 'student@example.edu')

    _create_item(test_db, user_id,
                 title='Backpack', category='bags', listing_type='lost')
    _create_item(test_db, user_id,
                 title='Laptop', category='electronics', listing_type='found')

    response = client.get('/posts/?category=bags&listing_type=LOST')

    assert response.status_code == 200

    posts = response.get_json()['posts']
    assert len(posts) == 1
    assert posts[0]['title'] == 'Backpack'

def test_get_posts_reject_invalid_listing_type(client):
    response = client.get('/posts/?listing_type=other')

    assert response.status_code == 400

def test_get_post_returns_existing_item(client, test_db):
    user_id = _create_user(test_db, 'student@example.edu')
    post_id = _create_item(test_db, user_id)    # default item values

    response = client.get(f'/posts/{post_id}')

    assert response.status_code == 200
    assert response.get_json()['id'] == post_id
    assert response.get_json()['title'] == 'Backpack'

def test_get_post_invalid_item(client):
    response = client.get('/posts/9999')

    assert response.status_code == 404

## CREATE POST TESTS
# ---------------------

def test_create_post_requires_login(client):
    response = client.post('/posts/')

    assert response.status_code == 401

def test_create_post_success(client, test_db):
    user_id = _create_user(test_db, 'student@example.edu')
    _login(client, 'student@example.edu')

    response = client.post('/posts/', json=_valid_post_data())

    assert response.status_code == 201

    created_post = response.get_json()['post']

    assert created_post['title'] == 'Lost wallet'
    assert created_post['listing_type'] == 'lost'

    saved_item = test_db.session.get(Item, created_post['id'])

    assert saved_item is not None
    assert saved_item.user_id == user_id

def test_create_post_reject_invalid_title(client, test_db):
    _create_user(test_db, 'student@example.edu')
    _login(client, 'student@example.edu')

    data = _valid_post_data()
    data['title'] = "  "

    response = client.post('/posts/', json=data)

    assert response.status_code == 400
    assert 'title' in response.get_json()['errors']

def test_create_post_reject_user_id_from_client(client, test_db):
    _create_user(test_db, 'student@example.edu')
    _login(client, 'student@example.edu')

    data = _valid_post_data()
    data['user_id'] = 999

    response = client.post('/posts/', json=data)

    assert response.status_code == 400
    assert 'body' in response.get_json()['errors']

## UPDATE POST TESTS
# ----------------------

def test_update_post_requires_login(client):
    response = client.patch('/posts/1', json={'title': 'Updated title'})

    assert response.status_code == 401

def test_update_post_changes_only_submitted_fields(client, test_db):
    _create_user(test_db, 'student@example.edu')
    post_id = _create_item(test_db, 1)

    _login(client, 'student@example.edu')

    response = client.patch(f'/posts/{post_id}', json={'description': 'Red backpack'}
    )

    assert response.status_code == 200

    updated_post = response.get_json()['post']

    assert updated_post['description'] == 'Red backpack'

    assert updated_post['title'] == 'Backpack'
    assert updated_post['category'] == 'bags'

def test_update_post_forbids_non_owner(client, test_db):
    owner_id = _create_user(test_db, 'student@example.edu')
    _create_user(test_db, 'other@example.edu')

    post_id = _create_item(test_db, owner_id)

    _login(client, 'other@example.edu')

    response = client.patch(f'/posts/{post_id}', json={'title': 'Unauthorized change'})

    assert response.status_code == 403

def test_update_post_reject_empty_data(client, test_db):
    _create_user(test_db, 'student@example.edu')
    post_id = _create_item(test_db, 1)

    _login(client, 'student@example.edu')

    response = client.patch(f'/posts/{post_id}', json={})

    assert response.status_code == 400

## DELETE POST TESTS
# -------------------

def test_delete_post_requires_login(client):
    response = client.delete('/posts/1')

    assert response.status_code == 401

def test_delete_post_success(client, test_db):
    _create_user(test_db, 'student@example.edu')
    post_id = _create_item(test_db, 1)

    _login(client, 'student@example.edu')

    response = client.delete(f'/posts/{post_id}')

    assert response.status_code == 204
    assert response.data == b''

    test_db.session.expire_all()

    assert test_db.session.get(Item, post_id) is None

def test_delete_post_forbids_non_owner(client, test_db):
    owner_id = _create_user(test_db, 'student@example.edu')
    _create_user(test_db, 'other@example.edu')

    post_id = _create_item(test_db, owner_id)

    _login(client, 'other@example.edu')

    response = client.delete(f'/posts/{post_id}')

    assert response.status_code == 403

    test_db.session.expire_all()

    assert test_db.session.get(Item, post_id) is not None