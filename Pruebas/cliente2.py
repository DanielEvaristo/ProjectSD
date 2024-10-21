import threading
import socket
import time
from tkinter import *
from tkinter import scrolledtext
from tkinter import messagebox
from tkinter import filedialog
import os
from PIL import Image, ImageTk
from cryptography.fernet import Fernet


# Leer la clave de encriptación desde el archivo
def cargar_clave():
    try:
        with open('encryption.key', 'rb') as key_file:
            return key_file.read()
    except FileNotFoundError:
        print("Archivo 'encryption.key' no encontrado. Los mensajes no se podrán desencriptar.")
        return None

clave = cargar_clave()
cipher_suite = Fernet(clave) if clave else None



# Crear la ventana de la interfaz gráfica
def centrar_ventana(ventana, width, height):
    # Calcular el tamaño de la pantalla y las coordenadas para centrar la ventana
    screen_width = ventana.winfo_screenwidth()
    screen_height = ventana.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    ventana.geometry(f"{width}x{height}+{x}+{y}")

ventana = Tk()
ventana.title("Mensajería UAQ")
ventana.resizable(0, 0)
ventana.iconbitmap("Logo.ico")
ventana.config(bg="gray")
ventana.withdraw()  # Oculta la ventana principal inicialmente
centrar_ventana(ventana,400,400)

# Variables de configuración inicial
discovery_host = '192.168.16.116'
discovery_port = 5000
host = '192.168.16.116'

# Asignar un puerto automáticamente
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((host, 0))
port = server.getsockname()[1]
server.listen()

# Lista de peers conectados y el historial de mensajes recientes
peers = []
message_history = set()
alias = ""
running = True  # Variable para controlar el estado de conexión del cliente

# Función para registrar el Peer en el servidor de descubrimiento
def register_with_discovery_server():
    try:
        discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        discovery_socket.connect((discovery_host, discovery_port))
        peer_info = f"{host}:{port}"
        discovery_socket.send(peer_info.encode('utf-8'))
        
        # Recibir lista de peers
        data = discovery_socket.recv(4096).decode('utf-8')
        peer_list = data.split('\n')
        
        print("Connected peers from discovery server:")
        for peer in peer_list:
            if peer != peer_info:
                ip, peer_port = peer.split(':')
                connect_to_peer(ip, int(peer_port))
        
        discovery_socket.close()
    except Exception as e:
        print(f"Could not connect to discovery server: {e}")

# Función para escuchar conexiones entrantes
def peer_receive():
    while running:
        try:
            client, address = server.accept()
            print(f"Connection established with {str(address)}")
            peers.append(client)
            thread = threading.Thread(target=handle_peer, args=(client, address))
            thread.start()
        except OSError:
            break

def show_image(image_path, alias):
    try:
        # Mostrar el alias sobre la imagen
        chat_window.config(state=NORMAL)
        chat_window.insert(END, f"{alias}:\n", 'sent')

        # Cargar y mostrar la imagen
        img = Image.open(image_path)
        img.thumbnail((150, 150))
        img_tk = ImageTk.PhotoImage(img)
        label = Label(chat_window, image=img_tk)
        label.image = img_tk
        chat_window.window_create(END, window=label)
        chat_window.insert(END, "\n\n")  # Salto de línea después de la imagen
        chat_window.config(state=DISABLED)
        chat_window.yview(END)

    except Exception as e:
        print(f"Error al mostrar la imagen: {e}")


# Función para manejar mensajes de los peers conectados
def handle_peer(peer, address):
    while running:
        try:
            header = peer.recv(3).decode('utf-8')
            if header == "ENC":
                encrypted_message = peer.recv(1024).decode('utf-8')
                if clave:
                    try:
                        decrypted_message = cipher_suite.decrypt(encrypted_message.encode('utf-8')).decode('utf-8')
                        if decrypted_message and decrypted_message not in message_history:
                            message_history.add(decrypted_message)
                            display_message(decrypted_message, 'received')
                    except Exception as e:
                        print(f"Error al desencriptar mensaje: {e}")
                        display_message("Mensaje cifrado no legible.", 'received')
                else:
                    display_message("Mensaje cifrado no legible (sin clave).", 'received')

            elif header == "MSG":
                message = peer.recv(1024).decode('utf-8')
                if message and message not in message_history:
                    message_history.add(message)
                    display_message(message, 'received')

            elif header == "IMG":
                # Manejar imágenes, manteniendo la lógica para intentar descifrar solo si se tiene clave
                image_size = int(peer.recv(10).decode('utf-8'))
                alias = peer.recv(32).decode('utf-8').strip()
                image_data = b''
                received_size = 0

                while received_size < image_size:
                    block = peer.recv(min(4096, image_size - received_size))
                    if not block:
                        break
                    image_data += block
                    received_size += len(block)

                if received_size == image_size:
                    if clave:
                        try:
                            decrypted_image_data = cipher_suite.decrypt(image_data)
                            os.makedirs('imagenes_recibidas', exist_ok=True)
                            image_path = os.path.join('imagenes_recibidas', f"imagen_{int(time.time())}.jpg")
                            with open(image_path, 'wb') as img_file:
                                img_file.write(decrypted_image_data)
                            show_image(image_path, alias)
                        except Exception as e:
                            print(f"Error al desencriptar imagen: {e}")
                            display_message("Imagen recibida, pero no se pudo desencriptar.", 'received')
                    else:
                        # Si no hay clave, guardar la imagen tal cual y mostrarla en texto plano
                        os.makedirs('imagenes_recibidas', exist_ok=True)
                        image_path = os.path.join('imagenes_recibidas', f"imagen_{int(time.time())}.jpg")
                        with open(image_path, 'wb') as img_file:
                            img_file.write(image_data)
                        show_image(image_path, alias)
                else:
                    print("Error al recibir la imagen completa.")
            else:
                print(f"Tipo de mensaje desconocido: {header}")
        except Exception as e:
            print(f"Error al manejar el peer {address}: {e}")
            disconnection_message = f"{address} se ha desconectado."
            display_message(disconnection_message, 'disconnect')
            peers.remove(peer)
            peer.close()
            break


# Función para enviar mensajes a todos los peers
def broadcast(message, sender):
    for peer in peers:
        if peer != sender:
            try:
                peer.send(message.encode('utf-8'))
            except:
                peer.close()
                peers.remove(peer)

# Función para conectarse a otros peers
def connect_to_peer(peer_ip, peer_port):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((peer_ip, peer_port))
    peers.append(client)
    print(f"Connected to peer at {peer_ip}:{peer_port}")
    thread = threading.Thread(target=handle_peer, args=(client, (peer_ip, peer_port)))
    thread.start()

# Función para enviar mensajes manualmente
def send_message():
    raw_message = mensaje_entry.get()
    if raw_message:
        message = f"{alias}: {raw_message}"
        
        if clave:
            encrypted_message = cipher_suite.encrypt(message.encode('utf-8'))
            full_message = "ENC" + encrypted_message.decode('utf-8')
        else:
            full_message = "MSG" + message  # Envía sin cifrar si no hay clave
        
        message_history.add(message)
        broadcast(full_message, None)
        display_message(message, 'sent')
        mensaje_entry.delete(0, END)


# Función para mostrar el mensaje en la ventana de chat con colores diferenciados
def display_message(message, message_type):
    chat_window.config(state=NORMAL)
    if message_type == 'sent':
        chat_window.insert(END, message + "\n", 'sent')
    elif message_type == 'received':
        chat_window.insert(END, message + "\n", 'received')
    elif message_type == 'disconnect':
        chat_window.insert(END, message + "\n", 'disconnect')
    chat_window.config(state=DISABLED)
    chat_window.yview(END)
    


# Función para iniciar la aplicación después de ingresar el alias
def iniciar_chat():
    global alias
    alias = alias_entry.get().strip()
    if alias:
        if not clave:
            messagebox.showwarning("Advertencia", "Tus mensajes no están protegidos, ya que no tienes la clave de encriptación.")
        alias_window.destroy()
        ventana.deiconify()  # Mostrar la ventana principal
        mensaje_entry.focus_set()  # Coloca el foco en el cuadro de entrada del mensaje
        register_with_discovery_server()
        receive_thread = threading.Thread(target=peer_receive)
        receive_thread.start()
    else:
        messagebox.showwarning("Alias requerido", "Por favor, ingresa un alias.")


# Función para salir del chat
def salir_chat():
    global running
    running = False
    disconnect_message = f"{alias} ha salido del chat."
    display_message(disconnect_message, 'disconnect')
    broadcast(disconnect_message, None)
    for peer in peers:
        peer.close()
    server.close()
    ventana.destroy()
    
def send_image():
    try:
        image_path = filedialog.askopenfilename(title="Selecciona una imagen", filetypes=[("Image files", "*.jpg;*.jpeg;*.png")])
        if not image_path:
            print("No se seleccionó ninguna imagen.")
            return

        with open(image_path, 'rb') as img_file:
            image_data = img_file.read()

        if clave:
            encrypted_image_data = cipher_suite.encrypt(image_data)
            image_size = len(encrypted_image_data)
        else:
            # Enviar la imagen sin cifrar
            encrypted_image_data = image_data
            image_size = len(image_data)

        # Mostrar la imagen en el chat del emisor con su alias
        show_image(image_path, alias)

        for peer in peers:
            try:
                peer.send("IMG".encode('utf-8'))
                peer.send(str(image_size).zfill(10).encode('utf-8'))
                peer.send(alias.encode('utf-8').ljust(32))
                peer.sendall(encrypted_image_data)
                print(f"Imagen de {image_size} bytes enviada a {peer.getpeername()}")
            except Exception as e:
                print(f"Error al enviar la imagen al peer {peer.getpeername()}: {e}")
                peer.close()
                peers.remove(peer)
    except Exception as e:
        print(f"Error al seleccionar o enviar la imagen: {e}")







# Ventana de entrada para el alias
alias_window = Toplevel(ventana)
alias_window.title("Ingresar Alias")
alias_window.iconbitmap("Logo.ico")
centrar_ventana(alias_window,250,100)
alias_window.resizable(0, 0)
alias_label = Label(alias_window, text="Ingresa tu alias:")
alias_label.pack(pady=10)
alias_entry = Entry(alias_window)
alias_entry.pack(pady=5)
alias_entry.focus_force()  # Coloca el foco en el cuadro de entrada del alias
alias_button = Button(alias_window, text="Iniciar", command=iniciar_chat)
alias_button.pack(pady=5)
alias_window.protocol("WM_DELETE_WINDOW", ventana.quit)

# Vincula la tecla Enter al botón "Iniciar"
alias_entry.bind("<Return>", lambda _: alias_button.invoke())

# Elementos de la interfaz gráfica principal
chat_window = scrolledtext.ScrolledText(ventana, width=50, height=15, bg="white")
chat_window.config(state=DISABLED)
chat_window.tag_config('sent', background="lightgreen")
chat_window.tag_config('received', background="lightgrey")
chat_window.tag_config('disconnect', background="red")
chat_window.pack(pady=10)

mensaje_entry = Entry(ventana, width=40)
mensaje_entry.pack(pady=5)
send_button = Button(ventana, text="Enviar", command=send_message)
send_button.pack(pady=5)
# Botón para enviar imágenes
image_button = Button(ventana, text="Enviar Imagen", command=send_image)
image_button.pack(pady=5)

salir_button = Button(ventana, text="Salir", command=salir_chat, bg="red", fg="white")
salir_button.pack(pady=5)

# Vincula la tecla Enter al botón "Enviar"
mensaje_entry.bind("<Return>", lambda _: send_button.invoke())

# Correr la ventana principal de la interfaz gráfica
ventana.mainloop()