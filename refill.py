import sys
import requests
import xml.etree.ElementTree as ET

SOAP_ENDPOINT = "https://bancamovil.provincial.com:42443/BMTranslator-war/CallSoap"

def get_bbva_session():
    return "1551880752MQsAiQ02dQjIwpFYUP99"

def get_user_agent():
    return "4442ACC96052839EB67DE9BC61D9822619E46E7B075697DF323D6B0A8F9EEC17;Android;BLURRYDEV;Redmi 5A;720x1280;Android;7.1.2;BMES;4.3;xhdpi"

def get_headers():
    return {
        "BBVA-Session": get_bbva_session(),
        "BBVA-User-Agent": get_user_agent(),
        "User-Agent": get_user_agent(),
        "Accept-Language": "spa",
        "Content-Type": "application/xml",
        "Accept": "application/xml",
        "Accept-Charset": "UTF-8"
    }

def import_secrets():
    file = open(".secrets")

    secrets = {}

    for line in file:
        k,v = line.split("=")

        secrets[k.strip()] = v.strip()

    return secrets

session = requests.session()

session.headers.update(get_headers())

secrets = import_secrets()

def do_auth(user, passwd):
    """
    Should return among a few things: card number, session ID, client ID
    """
    payload = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <login>
    <fase>1</fase>
    <tarjeta>V{}</tarjeta>
    <clave>{}</clave>
    <version>3</version>
    </login>""".format(user, passwd.upper())

    response = session.post("https://bancamovil.provincial.com:42443/BMTranslator-war/CallAuthentication", data=payload)

    root = parse_response(response.text)

    return {
        "tarjeta": root.find("./tarjeta").text,
        "cliente": root.find("./cliente").text,
        "idsesion-host": root.find("./idsesion-host").text,
        "id-esion-dist": root.find("./idsesion-dist").text,
        "tarj-metrica": root.find("./tarj-metrica").text,
    }


def get_account_details(auth_data):
    """
        Using the data gathered during auth we request other account details like the bank account number
    """
    payload = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <bbva>
    <cod>BM2501</cod>
    <idSesion>{idSesionHost}</idSesion>
    <numTarjeta>{numTarjeta}</numTarjeta>
    <numCliente>{idSesionHost}</numCliente>
    <indCuentas>1</indCuentas>
    <indTarjetas>1</indTarjetas>
    <indTarjetas>0</indTarjetas>
    <indTarjetasX>1</indTarjetasX>
    <indFideicomisos>1</indFideicomisos>
    <indFondosMutuales>1</indFondosMutuales>
    <indPrestamos>1</indPrestamos>
    <indInversiones>1</indInversiones>
    <indLCI>1</indLCI>
    </bbva>
    """.format(idSesionHost=auth_data['idsesion-host'], numTarjeta=auth_data['tarjeta'])

    response = session.post(SOAP_ENDPOINT, data=payload)

    root = parse_response(response.text)

    return extract_client_data(root)

def parse_response(xml):
    """
    Converts the response into an XML element
    """
    # Uncomment for debugging
    # print("Parsing xml: {}".format(xml))
    return ET.fromstring(xml)

def extract_client_data(root):
    if root.tag != "BM2501":
        print("Unexpected root tag {} in xml \n\n".format(root.tag))
    
    return {
        "idUser": xpath(root, "./regCliente/idUser"),
        "numCedula": xpath(root, "./regCliente/numCedula"),
        "indCedula": xpath(root, "./regCliente/indCedula"),
        "numTarjeta": xpath(root, "./regCliente/numTarjeta"),
        "numCuenta": xpath(root, "./lisCuentas/numCuenta"),
        "tipoCuenta": xpath(root, "./lisCuentas/codTipo"),
    }

def request_refill(session_data, number, amount):
    payload = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<bbva>
    <cod>BM1121</cod>
    <idSesion>{idSesionHost}</idSesion>
    <numTarjeta>{numTarjeta}</numTarjeta>
    <numCliente>{idSesionHost}</numCliente>
    <idUser>{idUser}</idUser>
    <claveEspecial>{claveEspecial}</claveEspecial>
    <numTelefono>{number}</numTelefono>
    <monto>{amount}</monto>
    <tipPago>1</tipPago>
    <cantPuntos>0</cantPuntos>
    <tipoCuenta>{tipoCuenta}</tipoCuenta>
    <numCuenta>{numCuenta}</numCuenta>
    <monPuntos></monPuntos>
    <indCedula>{indCedula}</indCedula>
    <numCedula>{numCedula}</numCedula>
    </bbva>"""

    payload_data = {
        "idSesionHost": session_data["idsesion-host"],
        "numTarjeta": session_data["numTarjeta"],
        "idUser": session_data["idUser"],
        "claveEspecial": session_data["claveEspecial"],
        "tipoCuenta": session_data["tipoCuenta"],
        "numCuenta": session_data["numCuenta"],
        "indCedula": session_data["indCedula"],
        "numCedula": session_data["numCedula"],
        "amount": amount,
        "number": number
    }

    payload = payload.format(**payload_data)

    response = session.post(SOAP_ENDPOINT, data=payload)

    root = parse_response(response.text)

    if xpath(root, "./codRespuesta") != "0":
        print("Algo salio mal.")
        des = root.find("./desRespuesta")

        if des is not None:
            print("Mensaje del banco: {}".format(des.text))
    else:
        print("Recarga exitosa.")

    return root

def xpath(root, xpath):
    """
    Returns the text of the first element found using xpath
    """
    return root.find(xpath).text

def print_balance(root):
    print("Available: {} VES".format(root.find("./lisCuentas/monDisponible").text))


if __name__ == "__main__":
    print("Intentando iniciar sesion en BBVA...")
    auth_data = do_auth(secrets['cedula'], secrets['clave'])
    print("Sesion iniciada. Obteniendo datos de cuenta.")
    account_data = get_account_details(auth_data)
    print("Datos de cuenta obtenidos, solicitado pago de servicio")
    session_data = {
        **auth_data,
        **account_data,
        "claveEspecial": secrets['clave_especial']
    }

    numero = secrets['numero']
    
    monto = sys.argv[1] if sys.argv[0] is not None else secrets['monto']

    print("Intentando recarga Movistar por VES {}".format(monto))
    request_refill(session_data, numero, monto)