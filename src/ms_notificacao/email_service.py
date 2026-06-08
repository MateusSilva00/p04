import resend
from loguru import logger

DESTINATARIO_FIXO = "mur1lol.mbc@gmail.com"


class EmailService:
    """
    Serviço de envio de e-mails via Resend para notificações de promoções.
    """

    def __init__(self, api_key: str, from_email: str = "onboarding@resend.dev"):
        resend.api_key = api_key
        self.from_email = from_email
        logger.info(f"EmailService inicializado (remetente: {self.from_email})")

    def enviar_promocao_publicada(self, payload: dict) -> None:
        """Envia e-mail notificando que a promoção foi aprovada e publicada."""
        destinatario = payload.get("loja_email")
        if not destinatario:
            logger.warning("Payload sem 'loja_email', e-mail não enviado.")
            return

        nome = payload.get("nome_produto", "Produto")
        categoria = payload.get("categoria", "N/A")
        preco = payload.get("preco", 0)
        loja = payload.get("loja", "N/A")
        id_promo = payload.get("id_promocao", "N/A")

        html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">✅ Promoção Publicada!</h1>
            </div>
            <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 12px 12px;">
                <p style="color: #333; font-size: 16px;">
                    Sua promoção foi aprovada e já está visível para os consumidores!
                </p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #dee2e6; color: #666;">
                            <strong>Produto</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #dee2e6; color: #333;">
                            {nome}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #dee2e6; color: #666;">
                            <strong>Categoria</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #dee2e6; color: #333;">
                            {categoria}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #dee2e6; color: #666;">
                            <strong>Preço</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #dee2e6; color: #333;
                                   font-weight: bold; color: #28a745;">
                            R$ {preco:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #dee2e6; color: #666;">
                            <strong>Loja</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #dee2e6; color: #333;">
                            {loja}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; color: #666;">
                            <strong>ID</strong></td>
                        <td style="padding: 10px; color: #999; font-family: monospace;">
                            {id_promo}</td>
                    </tr>
                </table>
                <p style="color: #666; font-size: 13px; text-align: center; margin-top: 20px;">
                    Sistema de Promoções — Sistemas Distribuídos UTFPR
                </p>
            </div>
        </div>
        """

        self._enviar(
            to=destinatario,
            subject=f"✅ Promoção Publicada: {nome}",
            html=html,
        )

    def enviar_hot_deal(self, payload: dict) -> None:
        """Envia e-mail notificando que a promoção virou Hot Deal."""
        destinatario = payload.get("loja_email")
        if not destinatario:
            logger.warning("Payload sem 'loja_email', e-mail de hot deal não enviado.")
            return

        nome = payload.get("nome_produto", "Produto")
        score = payload.get("score", "?")
        id_promo = payload.get("id_promocao", "N/A")

        html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                        padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px;">🔥 HOT DEAL!</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 16px;">
                    Sua promoção virou destaque!
                </p>
            </div>
            <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 12px 12px;">
                <div style="background: white; border-radius: 8px; padding: 20px;
                            border-left: 4px solid #f5576c; margin-bottom: 20px;">
                    <h2 style="margin: 0 0 8px 0; color: #333;">{nome}</h2>
                    <p style="margin: 0; color: #666;">
                        Atingiu <strong style="color: #f5576c; font-size: 20px;">{score}</strong>
                        votos positivos!
                    </p>
                </div>
                <p style="color: #333; font-size: 15px; line-height: 1.6;">
                    Parabéns! Sua promoção <strong>{nome}</strong> recebeu avaliações
                    muito positivas da comunidade e agora está sendo exibida como
                    <strong style="color: #f5576c;">destaque</strong> para todos os usuários.
                </p>
                <p style="color: #999; font-size: 12px; font-family: monospace;">
                    ID: {id_promo}
                </p>
                <p style="color: #666; font-size: 13px; text-align: center; margin-top: 20px;">
                    Sistema de Promoções — Sistemas Distribuídos UTFPR
                </p>
            </div>
        </div>
        """

        self._enviar(
            to=destinatario,
            subject=f"🔥 HOT DEAL: {nome} virou destaque!",
            html=html,
        )

    def _enviar(self, to: str, subject: str, html: str) -> None:
        """Wrapper interno para envio via Resend."""
        destinatario_real = DESTINATARIO_FIXO
        try:
            result = resend.Emails.send(
                {
                    "from": self.from_email,
                    "to": [destinatario_real],
                    "subject": subject,
                    "html": html,
                }
            )
            logger.info(f"📧 E-mail enviado para {to} | ID: {result.get('id', '?')}")
        except Exception as e:
            logger.error(f"❌ Falha ao enviar e-mail para {to}: {e}")
