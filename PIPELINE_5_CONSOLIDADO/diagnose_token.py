import os, json, requests, sys

ORDER_TEST = os.getenv('ORDER_TEST', '').strip()

CANDIDATE_PATHS = []
if os.getenv('TOKEN_PATH'):
    CANDIDATE_PATHS.append(os.getenv('TOKEN_PATH'))
# project config
CANDIDATE_PATHS.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'token.json')))
# legacy GUI path (guess from previous code)
CANDIDATE_PATHS.append(r'C:\\Users\\Mundo Outdoor\\Desktop\\Develop_Mati\\Escritor Meli\\token.json')


def red(s):
    return (s or '')[:6] + '...' if s else ''


def try_token(path):
    try:
        if not os.path.exists(path):
            return {'exists': False}
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        at = data.get('access_token', '')
        rt = data.get('refresh_token')
        cid = data.get('client_id')
        cs = data.get('client_secret')
        uid = data.get('user_id')
        out = {
            'exists': True,
            'access_token_len': len(at),
            'has_refresh_token': bool(rt),
            'has_client_id': bool(cid),
            'has_client_secret': bool(cs),
            'user_id': uid,
            'access_token_prefix': red(at)
        }
        if at:
            # users/me
            try:
                r = requests.get('https://api.mercadolibre.com/users/me', headers={'Authorization': f'Bearer {at}'}, timeout=15)
                out['users_me_status'] = r.status_code
                if r.status_code == 200:
                    me = r.json()
                    out['me_id'] = me.get('id')
                    out['me_nickname'] = me.get('nickname')
                # test notes if ORDER_TEST present
                if ORDER_TEST:
                    rn = requests.get(f'https://api.mercadolibre.com/orders/{ORDER_TEST}/notes', headers={'Authorization': f'Bearer {at}'}, params={'role': 'seller'}, timeout=15)
                    out['notes_status'] = rn.status_code
            except Exception as e:
                out['request_error'] = str(e)
        return out
    except Exception as e:
        return {'exists': False, 'error': str(e)}


def main():
    print('ORDER_TEST=', ORDER_TEST)
    for p in CANDIDATE_PATHS:
        res = try_token(p)
        print('---')
        print('path:', p)
        for k, v in res.items():
            print(f'{k}: {v}')

if __name__ == '__main__':
    main()
