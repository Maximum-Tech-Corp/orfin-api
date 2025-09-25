from rest_framework.serializers import ValidationError


def validate_cpf(cpf):
    """
    Validação de CPF usando o algoritmo de dígitos verificadores.
    Retorna CPF (only numbers) se válido.
    Lança ValidationError se inválido.
    """
    # Remove formatting
    cpf_clean = ''.join(filter(str.isdigit, cpf))

    # Check if has 11 digits
    if len(cpf_clean) != 11:
        raise ValidationError("CPF deve conter exatamente 11 números.")

    # Check if all digits are the same
    if cpf_clean == cpf_clean[0] * 11:
        raise ValidationError({"CPF inválido."})

    # Calculate first check digit
    sum_digits = sum(int(cpf_clean[i]) * (10 - i) for i in range(9))
    first_digit = (sum_digits * 10) % 11
    if first_digit == 10:
        first_digit = 0

    # Calculate second check digit
    sum_digits = sum(int(cpf_clean[i]) * (11 - i) for i in range(10))
    second_digit = (sum_digits * 10) % 11
    if second_digit == 10:
        second_digit = 0

    # Verify calculated digits
    if not (cpf_clean[9] == str(first_digit) and cpf_clean[10] == str(second_digit)):
        raise ValidationError("CPF inválido.")

    return cpf_clean
