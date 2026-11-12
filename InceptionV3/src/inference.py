import os
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import torch.nn.functional as F

# ==========================================
# 1. CONFIGURACIÓN Y PARÁMETROS
# ==========================================
MODEL_PATH = "mejor_modelo_bach.pth"
NUM_CLASSES = 4
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Clases ordenadas 
CLASS_NAMES = ['benign', 'insitu', 'invasive', 'normal']

print(f"Usando dispositivo para inferencia: {DEVICE}")

# ==========================================
# 2. TRANSFORMACIONES DE VALIDACIÓN/TEST
# ==========================================
# Idénticas a las val_transforms
inference_transforms = transforms.Compose([
    transforms.Resize((299, 299)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# ==========================================
# 3. CARGAR Y CONFIGURAR EL MODELO
# ==========================================
def cargar_modelo(model_path):
    print("Inicializando arquitectura Inception-V3...")

    model = models.inception_v3(weights=None) # se cargan los pesos del finetuning
    
    if model.AuxLogits is not None:
        num_ftrs_aux = model.AuxLogits.fc.in_features
        model.AuxLogits.fc = nn.Linear(num_ftrs_aux, NUM_CLASSES)
        
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, NUM_CLASSES)
    
    # Cargar los pesos entrenados
    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path, map_location=DEVICE))
        print(f"Pesos cargados correctamente desde: {model_path}")
    else:
        raise FileNotFoundError(f"No se encontró el archivo de pesos en {model_path}. Asegúrate de haber entrenado el modelo.")
        
    model = model.to(DEVICE)
    model.eval() # Modo evaluación (apaga dropout y batchnorm, y solo devuelve una salida)
    return model

# ==========================================
# 4. PREDICCIÓN
# ==========================================
def predecir_imagen(image_path, model):
    try:
        # Abrir la imagen y asegurar que esté en RGB
        img = Image.open(image_path).convert('RGB')
        
        # Aplicar transformaciones y añadir dimensión de batch (1, C, H, W)
        img_tensor = inference_transforms(img).unsqueeze(0).to(DEVICE)
        
        # Inferencia sin calcular gradientes
        with torch.no_grad():
            outputs = model(img_tensor)
            # Pasamos los logits por un Softmax para obtener porcentajes de confianza
            probabilities = F.softmax(outputs, dim=1)[0]
            
        # Obtener el índice con mayor probabilidad
        confidence, pred_idx = torch.max(probabilities, 0)
        
        clase_predicha = CLASS_NAMES[pred_idx.item()]
        porcentaje_confianza = confidence.item() * 100
        
        return clase_predicha, porcentaje_confianza, probabilities.cpu().numpy()
        
    except Exception as e:
        print(f"Error al procesar la imagen {image_path}: {e}")
        return None, None, None

# ==========================================
# 5. EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    modelo_bach = cargar_modelo(MODEL_PATH)
    
    # Puede ser una imagen individual o un directorio
    RUTA_TEST = "/home/azken/Workspace/Mario/Dataset/ICIAR2018_BACH_Challenge_TestDataset/ICIAR2018_BACH_Challenge_TestDataset/Photos/test2.tif" 
    
    print("\n" + "="*50)
    print("                RESULTADOS DE INFERENCIA")
    print("="*50)

    if os.path.isfile(RUTA_TEST):
        # archivo individual
        clase, conf, probs = predecir_imagen(RUTA_TEST, modelo_bach)
        if clase:
            print(f"Imagen: {os.path.basename(RUTA_TEST)}")
            print(f"-Predicción: {clase.upper()} ({conf:.2f}%)")
            print("Probabilidades por clase:")
            for c, p in zip(CLASS_NAMES, probs):
                print(f"   - {c}: {p*100:.2f}%")
                
    elif os.path.isdir(RUTA_TEST):
        # carpeta con múltiples imágenes
        extensiones_validas = ('.png', '.jpg', '.jpeg', '.tif', '.tiff')
        archivos = [os.path.join(RUTA_TEST, f) for f in os.listdir(RUTA_TEST) if f.lower().endswith(extensiones_validas)]
        
        if not archivos:
            print("No se encontraron imágenes válidas en la carpeta especificada.")
        else:
            for ruta_img in archivos:
                clase, conf, _ = predecir_imagen(ruta_img, modelo_bach)
                if clase:
                    print(f"{os.path.basename(ruta_img)} ➔ Muestra: {clase.upper()} | Confianza: {conf:.2f}%")
    else:
        print("La ruta provista en RUTA_TEST no es un archivo ni una carpeta válida. Modifica el script con una ruta real.")