import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms, models
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# ==========================================
# 1. CONFIGURACIÓN Y PARÁMETROS
# ==========================================
DATA_DIR = "/home/azken/Workspace/Mario/Dataset/ICIAR2018_BACH_Challenge/ICIAR2018_BACH_Challenge/Photos"
BATCH_SIZE = 16          # Inception-V3 a 299x299 consume bastante memoria de GPU
EPOCHS = 30
LEARNING_RATE = 0.0001
NUM_CLASSES = 4
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Usando dispositivo: {DEVICE}")

# ==========================================
# 2. TRANSFORMACIONES (DATA AUGMENTATION)
# ==========================================
train_transforms = transforms.Compose([
    transforms.Resize((299, 299)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(15),
    # Ajuste sutil de color para simular variaciones de tinción H&E
    transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

val_transforms = transforms.Compose([
    transforms.Resize((299, 299)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# ==========================================
# 3. CARGA DE DATOS Y SPLIT (TRAIN/VAL)
# ==========================================
# usando ImageFolder
full_dataset = datasets.ImageFolder(root=DATA_DIR)
print(f"Clases detectadas: {full_dataset.classes}")

#  split estratificado (mantiene proporción de clases)
targets = full_dataset.targets
train_idx, val_idx = train_test_split(
    range(len(targets)), 
    test_size=0.20, 
    stratify=targets, 
    random_state=42
)

# subsets aplicando respectivas transformaciones
train_dataset = Subset(full_dataset, train_idx)
val_dataset = Subset(full_dataset, val_idx)

# transformaciones x cada set
train_dataset.dataset.transform = train_transforms
val_dataset.dataset.transform = val_transforms

# DataLoaders
train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

print(f"Imágenes de entrenamiento: {len(train_dataset)} | Validación: {len(val_dataset)}")

# ==========================================
# 4. CONFIGURAR INCEPTION-V3 (FINE-TUNING)
# ==========================================
print("Cargando Inception-V3 preentrenado...")
model = models.inception_v3(weights='IMAGENET1K_V1')

# IMPORTANTE: Inception-V3 tiene dos salidas durante el entrenamiento (AuxLogits y la capa final).
# Se modifica la capa de salida auxiliar (AuxLogits)
if model.AuxLogits is not None:
    num_ftrs_aux = model.AuxLogits.fc.in_features
    model.AuxLogits.fc = nn.Linear(num_ftrs_aux, NUM_CLASSES)

# Modificamos la capa de salida principal
num_ftrs = model.fc.in_features
model.fc = nn.Linear(num_ftrs, NUM_CLASSES)

model = model.to(DEVICE)

# Pérdida y optimizador
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

# ==========================================
# 5. BUCLE DE ENTRENAMIENTO Y VALIDACIÓN
# ==========================================
best_val_acc = 0.0

# --- MODIFICACIÓN: Historiales de métricas ---
history = {
    'train_loss': [],
    'val_loss': [],
    'train_acc': [],
    'val_acc': []
}

for epoch in range(EPOCHS):
    print(f"\nÉpoca {epoch+1}/{EPOCHS}")
    
    # --- FASE DE ENTRENAMIENTO ---
    model.train()
    running_loss = 0.0
    running_corrects = 0
    
    for inputs, labels in tqdm(train_loader, desc="Entrenando"):
        inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
        
        optimizer.zero_grad()
        
        # Inception_v3 devuelve una tupla (salida_principal, salida_auxiliar) en modo train
        outputs, aux_outputs = model(inputs)
        loss1 = criterion(outputs, labels)
        loss2 = criterion(aux_outputs, labels)
        loss = loss1 + 0.3 * loss2 # Ponderación estándar para el clasificador auxiliar
        
        loss.backward()
        optimizer.step()
        
        _, preds = torch.max(outputs, 1)
        running_loss += loss.item() * inputs.size(0)
        running_corrects += torch.sum(preds == labels.data)
        
    epoch_loss = running_loss / len(train_dataset)
    epoch_acc = running_corrects.double() / len(train_dataset)
    
    # --- FASE DE VALIDACIÓN ---
    model.eval()
    val_loss = 0.0
    val_corrects = 0
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for inputs, labels in tqdm(val_loader, desc="Validando"):
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
            
            # En modo eval(), Inception_v3 solo devuelve la salida principal
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            
            _, preds = torch.max(outputs, 1)
            val_loss += loss.item() * inputs.size(0)
            val_corrects += torch.sum(preds == labels.data)
            
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            
    epoch_val_loss = val_loss / len(val_dataset)
    epoch_val_acc = val_corrects.double() / len(val_dataset)
    
    print(f"Train Loss: {epoch_loss:.4f} | Acc: {epoch_acc:.4f}")
    print(f"Val Loss: {epoch_val_loss:.4f} | Acc: {epoch_val_acc:.4f}")
    
    # --- MODIFICACIÓN: Almacenar métricas en el historial ---
    history['train_loss'].append(epoch_loss)
    history['val_loss'].append(epoch_val_loss)
    history['train_acc'].append(epoch_acc.item() if isinstance(epoch_acc, torch.Tensor) else epoch_acc)
    history['val_acc'].append(epoch_val_acc.item() if isinstance(epoch_val_acc, torch.Tensor) else epoch_val_acc)
    
    # Guardar el mejor modelo
    if epoch_val_acc > best_val_acc:
        best_val_acc = epoch_val_acc
        torch.save(model.state_dict(), 'mejor_modelo_bach.pth')
        print("Nuevo mejor modelo guardado")

# ==========================================
# --- MODIFICACIÓN: GRAFICAR PÉRDIDA Y ACCURACY ---
# ==========================================
print("\nGenerando gráficas de pérdida y precisión...")
plt.figure(figsize=(14, 5))

# Gráfica de Pérdida (Loss)
plt.subplot(1, 2, 1)
plt.plot(range(1, EPOCHS + 1), history['train_loss'], label='Train Loss', color='#1f77b4', linewidth=2)
plt.plot(range(1, EPOCHS + 1), history['val_loss'], label='Val Loss', color='#ff7f0e', linewidth=2)
plt.title('Pérdida por Época (Loss)', fontsize=12, fontweight='bold')
plt.xlabel('Época')
plt.ylabel('Pérdida')
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend()

# Gráfica de Precisión (Accuracy)
plt.subplot(1, 2, 2)
plt.plot(range(1, EPOCHS + 1), history['train_acc'], label='Train Acc', color='#2ca02c', linewidth=2)
plt.plot(range(1, EPOCHS + 1), history['val_acc'], label='Val Acc', color='#d62728', linewidth=2)
plt.title('Precisión por Época (Accuracy)', fontsize=12, fontweight='bold')
plt.xlabel('Época')
plt.ylabel('Precisión')
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend()

plt.tight_layout()
plt.savefig('graficas_rendimiento.png', dpi=300)
print("Gráficas guardadas como 'graficas_rendimiento.png'")


# ==========================================
# 6. EVALUACIÓN FINAL (MÉTRICAS MULTICLASE)
# ==========================================
print("\n╔════════════════════════════════════════════╗")
print("║         REPORTE DE EVALUACIÓN FINAL        ║")
print("╚════════════════════════════════════════════╝")

# Cargar los mejores pesos para evaluar
model.load_state_dict(torch.load('mejor_modelo_bach.pth'))
model.eval()

# Para el reporte final es recomendable recalcular predicciones con el mejor modelo,
# aquí mantiene la estructura original usando los valores de la última época.
print(classification_report(all_labels, all_preds, target_names=full_dataset.classes))

# Generar Matriz de Confusión
cm = confusion_matrix(all_labels, all_preds)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=full_dataset.classes, yticklabels=full_dataset.classes)
plt.xlabel('Predicho')
plt.ylabel('Real')
plt.title('Matriz de Confusión - Dataset BACH')
plt.savefig('matriz_confusion.png')
print("Matriz de confusión guardada como 'matriz_confusion.png'")