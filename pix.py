import mercadopago
import os
from dotenv import load_dotenv

load_dotenv()

sdk = mercadopago.SDK('APP_USR-2956233144708511-010415-2edfd397936731948451395a85d01505-1377932499')

def criar_pix(valor, descricao):
    payment_data = {
        "transaction_amount": float(valor),
        "description": descricao,
        "payment_method_id": "pix",
        "payer": {"email": "cliente@discord.com"}
    }

    payment = sdk.payment().create(payment_data)
    return payment["response"]

def verificar_pix(payment_id):
    payment = sdk.payment().get(payment_id)
    return payment["response"]["status"]