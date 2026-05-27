import base64
import logging
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

logger = logging.getLogger(__name__)


class CryptoService:
    @staticmethod
    def generate_key_pair() -> tuple[bytes, bytes]:
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

        public_key = private_key.public_key()

        pem_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pem_public = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return pem_private, pem_public

    @staticmethod
    def sign_message(private_key_pem: bytes, payload_bytes: bytes) -> str:
        """Assina um payload utilizando a chave privada."""
        private_key: RSAPrivateKey | ... = serialization.load_pem_private_key(  # type: ignore
            private_key_pem, password=None, backend=default_backend()
        )

        signature = private_key.sign(
            data=payload_bytes,
            padding=padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            algorithm=hashes.SHA256(),
        )

        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def verify_signature(public_key_pem: bytes, payload_byes: bytes, signature_b64: str) -> bool:
        """
        Verifica a assinatura digital utilizando a chave pública.
        """
        try:
            public_key: RSAPrivateKey | ... = serialization.load_pem_public_key(  # type: ignore
                data=public_key_pem, backend=default_backend()
            )

            signature_bytes = base64.b64decode(signature_b64)

            public_key.verify(
                signature_bytes,
                payload_byes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True

        except InvalidSignature:
            logger.warning("Assinatura inválida dectada!")
            return False
        except Exception as e:
            logger.error(f"Erro ao processar a verificação de assinatura: {e}")
            return False

    @staticmethod
    def load_or_generate_keys(
        service_name: str, keys_dir_name: str = "keys"
    ) -> tuple[bytes, bytes]:
        """
        Gerencia a persistência das chaves no disco para simular um cofre de chaves.
        """

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        keys_dir = os.path.join(base_dir, keys_dir_name)
        os.makedirs(keys_dir, exist_ok=True)

        priv_path = os.path.join(keys_dir, f"{service_name}_private.pem")
        pub_path = os.path.join(keys_dir, f"{service_name}_public.pem")

        if os.path.exists(priv_path) and os.path.exists(pub_path):
            with open(priv_path, "rb") as f_priv, open(pub_path, "rb") as f_pub:
                return f_priv.read(), f_pub.read()

        logger.info(f"Gerando novo par de chaves para o serviço: {service_name}")
        priv_key, pub_key = CryptoService.generate_key_pair()

        with open(priv_path, "wb") as f_priv, open(pub_path, "wb") as f_pub:
            f_priv.write(priv_key)
            f_pub.write(pub_key)

        return priv_key, pub_key
