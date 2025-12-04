# Generador_QR_colindante.py
import sys
import qrcode

def make_qr_lines(data):
    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    # Obtener el QR como lista de strings
    qr_lines = qr.get_matrix()
    
    # Usar bloques de media altura para compensar la forma rectangular de los caracteres
    # Procesar de 2 en 2 filas para crear bloques cuadrados
    result = []
    for i in range(0, len(qr_lines), 2):
        line = ""
        for j in range(len(qr_lines[i])):
            top = qr_lines[i][j] if i < len(qr_lines) else False
            bottom = qr_lines[i+1][j] if i+1 < len(qr_lines) else False
            
            if top and bottom:
                line += "█"  # Ambos llenos
            elif top and not bottom:
                line += "▀"  # Solo arriba
            elif not top and bottom:
                line += "▄"  # Solo abajo
            else:
                line += " "  # Ambos vacíos
        result.append(line)
    
    return result

if len(sys.argv) < 3:
    print("Uso: python generate_qr_side_by_side.py <URL1> <URL2>")
    sys.exit(1)

url1 = sys.argv[1]
url2 = sys.argv[2]

lines1 = make_qr_lines(url1)
lines2 = make_qr_lines(url2)

# Asegurarse de que tengan la misma altura
max_lines = max(len(lines1), len(lines2))

# Calcular el ancho de cada QR
width1 = len(lines1[0]) if lines1 else 0
width2 = len(lines2[0]) if lines2 else 0

# Rellenar con espacios para igualar alturas
while len(lines1) < max_lines:
    lines1.append(" " * width1)
while len(lines2) < max_lines:
    lines2.append(" " * width2)

# Imprimir lado a lado con espaciado adecuado
spacing = "  "  # Espacio entre QRs
for l1, l2 in zip(lines1, lines2):
    print(l1 + spacing + l2)
