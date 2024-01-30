from jinja2 import Environment, FileSystemLoader
import sqlite3

# Charger le modèle HTML
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('template.html')

# Connexion à la base de données
conn = sqlite3.connect('levels.db')
c = conn.cursor()

# Récupérer les données de la base de données
c.execute('SELECT * FROM levels')
data = c.fetchall()

# Générer le fichier HTML avec les données
output = template.render(data=data)

# Écrire le fichier HTML
with open('output.html', 'w') as f:
    f.write(output)
