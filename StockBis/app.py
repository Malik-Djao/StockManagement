"""
StockMaster Pro - Application de Gestion de Stock
Backend Flask avec SQLAlchemy
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import func

# ============================================
# CONFIGURATION DE L'APPLICATION
# ============================================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stock.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'votre-cle-secrete-super-securisee-2026'

db = SQLAlchemy(app)

# ============================================
# MODÈLES DE BASE DE DONNÉES
# ============================================

class Product(db.Model):
    """
    Modèle Product : Représente un produit dans l'inventaire
    - id : Identifiant unique
    - name : Nom du produit
    - stock_quantity : Quantité en stock
    - buying_price : Prix d'achat unitaire
    - selling_price : Prix de vente unitaire
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)
    buying_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    
    # Relation avec les ventes
    sales = db.relationship('Sale', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'


class Sale(db.Model):
    """
    Modèle Sale : Représente une vente effectuée
    - id : Identifiant unique
    - product_id : Référence au produit vendu
    - quantity_sold : Quantité vendue
    - sale_date : Date et heure de la vente (UTC)
    - profit_recorded : Profit figé au moment de la vente
    """
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    profit_recorded = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<Sale {self.id} - Product {self.product_id}>'


# ============================================
# ROUTES - DASHBOARD
# ============================================

@app.route('/')
def dashboard():
    """
    Page d'accueil : Tableau de bord avec statistiques hebdomadaires
    - CA Semaine : Chiffre d'affaires des 7 derniers jours
    - Bénéfice Semaine : Profit total des 7 derniers jours
    - Dernières ventes : 5 ventes les plus récentes
    """
    # Calcul de la date il y a 7 jours
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    # Récupération des ventes de la semaine
    weekly_sales = Sale.query.filter(Sale.sale_date >= week_ago).all()
    
    # Calcul du CA (Chiffre d'Affaires) de la semaine
    weekly_revenue = 0
    for sale in weekly_sales:
        product = Product.query.get(sale.product_id)
        weekly_revenue += product.selling_price * sale.quantity_sold
    
    # Calcul du bénéfice de la semaine (somme des profits enregistrés)
    weekly_profit = sum(sale.profit_recorded for sale in weekly_sales)
    
    # Récupération des 5 dernières ventes
    recent_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         weekly_revenue=weekly_revenue,
                         weekly_profit=weekly_profit,
                         recent_sales=recent_sales)


# ============================================
# ROUTES - INVENTAIRE
# ============================================

@app.route('/inventory')
def inventory():
    """
    Page Inventaire : Affiche tous les produits en stock
    """
    products = Product.query.all()
    return render_template('inventory.html', products=products)


@app.route('/inventory/add', methods=['POST'])
def add_product():
    """
    Ajouter un nouveau produit à l'inventaire
    """
    try:
        name = request.form.get('name')
        stock_quantity = int(request.form.get('stock_quantity', 0))
        buying_price = float(request.form.get('buying_price', 0))
        selling_price = float(request.form.get('selling_price', 0))
        
        # Création du nouveau produit
        new_product = Product(
            name=name,
            stock_quantity=stock_quantity,
            buying_price=buying_price,
            selling_price=selling_price
        )
        
        db.session.add(new_product)
        db.session.commit()
        
        flash(f'✅ Produit "{name}" ajouté avec succès !', 'success')
    except Exception as e:
        flash(f'❌ Erreur lors de l\'ajout du produit : {str(e)}', 'danger')
    
    return redirect(url_for('inventory'))


@app.route('/inventory/edit/<int:product_id>', methods=['POST'])
def edit_product(product_id):
    """
    Modifier un produit existant
    """
    try:
        product = Product.query.get_or_404(product_id)
        
        product.name = request.form.get('name')
        product.stock_quantity = int(request.form.get('stock_quantity', 0))
        product.buying_price = float(request.form.get('buying_price', 0))
        product.selling_price = float(request.form.get('selling_price', 0))
        
        db.session.commit()
        
        flash(f'✅ Produit "{product.name}" modifié avec succès !', 'success')
    except Exception as e:
        flash(f'❌ Erreur lors de la modification : {str(e)}', 'danger')
    
    return redirect(url_for('inventory'))


@app.route('/inventory/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """
    Supprimer un produit de l'inventaire
    """
    try:
        product = Product.query.get_or_404(product_id)
        product_name = product.name
        
        db.session.delete(product)
        db.session.commit()
        
        flash(f'✅ Produit "{product_name}" supprimé avec succès !', 'success')
    except Exception as e:
        flash(f'❌ Erreur lors de la suppression : {str(e)}', 'danger')
    
    return redirect(url_for('inventory'))


# ============================================
# ROUTES - CAISSE (POINT DE VENTE)
# ============================================

@app.route('/sale')
def sale_page():
    """
    Page Caisse : Formulaire de vente
    """
    products = Product.query.filter(Product.stock_quantity > 0).all()
    return render_template('pos.html', products=products)


@app.route('/sale/process', methods=['POST'])
def process_sale():
    """
    Traiter une vente
    LOGIQUE CRITIQUE : Calcul et enregistrement du profit au moment de la vente
    """
    try:
        product_id = int(request.form.get('product_id'))
        quantity_sold = int(request.form.get('quantity_sold'))
        
        # Récupération du produit
        product = Product.query.get_or_404(product_id)
        
        # Vérification du stock disponible
        if product.stock_quantity < quantity_sold:
            flash(f'❌ Stock insuffisant ! Disponible : {product.stock_quantity}', 'danger')
            return redirect(url_for('sale_page'))
        
        # CALCUL DU PROFIT (figé au moment de la vente)
        profit = (product.selling_price - product.buying_price) * quantity_sold
        
        # Création de l'enregistrement de vente
        new_sale = Sale(
            product_id=product_id,
            quantity_sold=quantity_sold,
            profit_recorded=profit
        )
        
        # Mise à jour du stock
        product.stock_quantity -= quantity_sold
        
        # Sauvegarde en base de données
        db.session.add(new_sale)
        db.session.commit()
        
        flash(f'✅ Vente enregistrée ! {quantity_sold} x {product.name} | Profit : {profit:.2f} FCFA', 'success')
    except Exception as e:
        flash(f'❌ Erreur lors de la vente : {str(e)}', 'danger')
    
    return redirect(url_for('sale_page'))


# ============================================
# API ENDPOINT (Optionnel - pour JS dynamique)
# ============================================

@app.route('/api/product/<int:product_id>')
def get_product_info(product_id):
    """
    Endpoint API pour récupérer les informations d'un produit (JSON)
    Utile pour afficher dynamiquement le prix en JavaScript
    """
    product = Product.query.get_or_404(product_id)
    return jsonify({
        'id': product.id,
        'name': product.name,
        'stock_quantity': product.stock_quantity,
        'buying_price': product.buying_price,
        'selling_price': product.selling_price
    })


# ============================================
# INITIALISATION DE LA BASE DE DONNÉES
# ============================================

def init_db():
    """
    Créer automatiquement la base de données et les tables
    au premier lancement de l'application
    """
    with app.app_context():
        db.create_all()
        print("✅ Base de données 'stock.db' créée avec succès !")


# ============================================
# LANCEMENT DE L'APPLICATION
# ============================================

if __name__ == '__main__':
    # Initialisation de la base de données
    init_db()
    
    # Lancement du serveur Flask en mode debug
    app.run(debug=True, host='0.0.0.0', port=5000)
