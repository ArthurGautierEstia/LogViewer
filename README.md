# KUKA RSI Log Viewer

Ce projet est une application graphique Python permettant d'analyser et de visualiser les logs XML issus de robots KUKA utilisant RSI.  
Elle permet d'extraire automatiquement toutes les valeurs numériques des trames XML, de les explorer, de générer des graphiques interactifs et d'exporter des rapports HTML.

---

## Fonctionnalités

- Interface graphique simple (Tkinter)
- Extraction automatique de tous les tags et attributs numériques des logs XML
- Visualisation interactive (courbes, histogrammes) avec Plotly
- Export HTML interactif multi-graphes
- Sélection facile des tags à analyser

---

## Installation

1. **Cloner le dépôt**

```bash
git clone https://github.com/ton-utilisateur/ton-repo.git
cd LogViewer
```

2. **Créer et activer un environnement virtuel**

Sous Windows :
```powershell
python -m venv venv
.\venv\Scripts\activate
```

3. **Installer les dépendances**

```bash
pip install -r requirements.txt
```

> **Remarque :**  
> Si tu utilises la visualisation embarquée dans Tkinter, installe aussi `tkinterhtml` :
> ```bash
> pip install tkinterhtml
> ```

---

## Utilisation

1. Lance l'application :

```bash
python logviewer.py
```

2. Clique sur **"Charger un fichier de log"** et sélectionne ton fichier `.log` contenant les trames XML.

3. Sélectionne un tag dans la liste déroulante pour afficher ses graphiques (courbe + histogramme).

4. Pour exporter tous les tags dans un rapport HTML interactif, clique sur "Oui" à la question après le chargement.

---

## Dépendances principales

- Python 3.8+
- tkinter
- plotly
- numpy
- tkinterhtml (optionnel, pour affichage HTML dans l'appli)

---

## Générer/mettre à jour le fichier requirements.txt

Après installation des paquets nécessaires dans ton environnement virtuel :

```bash
pip freeze > requirements.txt
```

---

## Structure du projet

```
LogViewer/
│
├── logviewer.py
├── requirements.txt
├── .gitignore
└── ...
```

---

## Aide

- Si tu rencontres un problème d'affichage des graphiques, vérifie que ton navigateur par défaut est bien configuré.
- Pour toute question ou bug, ouvre une issue sur le dépôt GitHub.

---

## Auteur

Arthur Gautier

---
