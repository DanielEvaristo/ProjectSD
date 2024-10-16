
import socket
import threading

# Configuración del servidor de descubrimiento
host = 'localhost' #localhost
port = 5000
buff = 1024

# Lista de los nodos que se conectan (IPs y puertos)
nodo = []

# Configuración del socket del servidor de descubrimiento
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((host, port))
server.listen()

# Función para manejar la conexión con un peer
def handle_peer(client):
    try:
        # Recibir IP y puerto del peer
        peer_info = client.recv(1024).decode('utf-8')
        nodo.append(peer_info)
        print(f"Peer added: {peer_info}")
        
        # Enviar la lista actualizada de peers al nuevo peer
        client.send('\n'.join(nodo).encode('utf-8'))
    except Exception as e:
        print(f"Error handling peer: {e}")
    finally:
        client.close()

# Función principal para aceptar conexiones de peers
def receive_peers():
    print("Discovery server is running...")
    while True:
        client, address = server.accept()
        print(f"Connection established with {address}")
        thread = threading.Thread(target=handle_peer, args=(client,))
        thread.start()

if __name__ == "__main__":
    receive_peers()