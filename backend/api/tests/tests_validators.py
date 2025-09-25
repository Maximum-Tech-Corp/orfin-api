from django.test import TestCase
from rest_framework.serializers import ValidationError

from backend.api.utils.validators import validate_cpf


class CPFValidatorTest(TestCase):
    """
    Testes para o validador de CPF
    """

    def test_valid_cpf_success(self):
        """Testa validação de CPF válido"""
        # CPF válido: 11144477735
        cpf_valido = "11144477735"
        result = validate_cpf(cpf_valido)
        self.assertEqual(result, cpf_valido)

    def test_valid_cpf_with_formatting(self):
        """Testa validação de CPF válido com formatação"""
        # CPF válido com formatação
        cpf_formatado = "111.444.777-35"
        result = validate_cpf(cpf_formatado)
        self.assertEqual(result, "11144477735")

    def test_cpf_invalid_length_short(self):
        """Testa CPF com menos de 11 dígitos"""
        cpf_curto = "1234567890"  # 10 dígitos

        with self.assertRaises(ValidationError) as cm:
            validate_cpf(cpf_curto)
        self.assertIn("CPF deve conter exatamente 11 números",
                      str(cm.exception))

    def test_cpf_invalid_length_long(self):
        """Testa CPF com mais de 11 dígitos"""
        cpf_longo = "123456789012"  # 12 dígitos

        with self.assertRaises(ValidationError) as cm:
            validate_cpf(cpf_longo)
        self.assertIn("CPF deve conter exatamente 11 números",
                      str(cm.exception))

    def test_cpf_all_same_digits(self):
        """Testa CPF com todos os dígitos iguais"""
        cpfs_invalidos = [
            "11111111111",
            "22222222222",
            "33333333333",
            "44444444444",
            "55555555555",
            "66666666666",
            "77777777777",
            "88888888888",
            "99999999999",
            "00000000000"
        ]

        for cpf in cpfs_invalidos:
            with self.assertRaises(ValidationError) as cm:
                validate_cpf(cpf)
            self.assertIn("CPF inválido", str(cm.exception))

    def test_cpf_first_check_digit_equals_10(self):
        """
        Testa CPF onde primeiro dígito verificador calculado é 10
        CPF onde a soma dos 9 primeiros dígitos * pesos resulta em resto 0
        Exemplo: 17578912003 -> primeiro dígito calculado seria 10, mas fica 0
        """
        cpf_test = "17578912003"  # CPF válido onde primeiro dígito é 0
        result = validate_cpf(cpf_test)
        self.assertEqual(result, cpf_test)

    def test_cpf_second_check_digit_equals_10(self):
        """
        Testa CPF onde segundo dígito verificador calculado é 10
        CPF onde o segundo dígito verificador calculado é 10, mas fica 0
        """
        cpf_test = "60017806330"  # CPF válido onde segundo dígito é 0
        result = validate_cpf(cpf_test)
        self.assertEqual(result, cpf_test)

    def test_cpf_invalid_check_digits(self):
        """
        Testa CPF com dígitos verificadores inválidos
        CPF com dígitos verificadores errados
        """
        cpf_invalido = "11144477799"  # Baseado no CPF válido 11144477735

        with self.assertRaises(ValidationError) as cm:
            validate_cpf(cpf_invalido)
        self.assertIn("CPF inválido", str(cm.exception))

    def test_cpf_invalid_first_check_digit_only(self):
        """Testa CPF com apenas o primeiro dígito verificador inválido"""
        cpf_invalido = "11144477745"  # Primeiro dígito errado (4 em vez de 3)

        with self.assertRaises(ValidationError) as cm:
            validate_cpf(cpf_invalido)
        self.assertIn("CPF inválido", str(cm.exception))

    def test_cpf_invalid_second_check_digit_only(self):
        """Testa CPF com apenas o segundo dígito verificador inválido"""
        cpf_invalido = "11144477736"  # Segundo dígito errado (6 em vez de 5)

        with self.assertRaises(ValidationError) as cm:
            validate_cpf(cpf_invalido)
        self.assertIn("CPF inválido", str(cm.exception))

    def test_cpf_with_letters_and_special_chars(self):
        """Testa CPF com letras e caracteres especiais"""
        cpf_com_letras = "111a444b777c35"
        result = validate_cpf(cpf_com_letras)
        # Deve extrair apenas os números e validar
        self.assertEqual(result, "11144477735")

    def test_cpf_empty_string(self):
        """Testa CPF vazio"""
        with self.assertRaises(ValidationError) as cm:
            validate_cpf("")
        self.assertIn("CPF deve conter exatamente 11 números",
                      str(cm.exception))

    def test_cpf_only_special_chars(self):
        """Testa CPF apenas com caracteres especiais"""
        with self.assertRaises(ValidationError) as cm:
            validate_cpf("...-/-")
        self.assertIn("CPF deve conter exatamente 11 números",
                      str(cm.exception))
