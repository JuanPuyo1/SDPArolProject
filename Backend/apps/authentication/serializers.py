from django.contrib.auth import get_user_model


def user_to_dict(user) -> dict:
    User = get_user_model()
    payload = {
        'id': user.pk,
        'user_id': getattr(user, 'user_id', ''),
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name() or user.username,
        'is_staff': user.is_staff,
        'date_joined': user.date_joined.isoformat(),
        'last_login': user.last_login.isoformat() if user.last_login else None,
    }
    if isinstance(user, User):
        payload.update({
            'company_id': user.company_id,
            'job_title': user.job_title,
            'visibility': user.visibility,
        })
    return payload
