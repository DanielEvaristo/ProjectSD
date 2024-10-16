from cryptography.fernet import Fernet

# Generar la clave y guardarla en un archivo
key = Fernet.generate_key()
with open('encryption.key', 'wb') as key_file:
    key_file.write(key)
print("Clave generada y guardada en 'encryption.key'.")
