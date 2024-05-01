from . import db
import flask_login
from sqlalchemy import func
from sqlalchemy.orm import aliased

# ADD NULLABLES AND LENGTHS FOR STR
class User(flask_login.UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(512), unique=True)
    password = db.Column(db.String(512))
    name = db.Column(db.String(512))
    recipes = db.relationship('Recipe', back_populates='user')
    photos = db.relationship('Photo', back_populates='user')
    ratings = db.relationship('Rating', back_populates='user')
    bookmarks = db.relationship('Bookmark', back_populates='user')

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(512))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', back_populates='recipes')
    description = db.Column(db.Text)
    cooking_time = db.Column(db.Integer)
    steps = db.relationship('Step', back_populates='recipe')
    bookmarks = db.relationship('Bookmark', back_populates='recipe')
    qIngredients = db.relationship('QIngredient', back_populates='recipe')
    photos = db.relationship('Photo', back_populates='recipe')
    ratings = db.relationship('Rating', back_populates = 'recipe')
    drinks = db.relationship('Drink', back_populates = 'recipe')

    def mean_rating(self):
        avg_rating = db.session.query(func.avg(Rating.value)).filter_by(recipe_id=self.id).scalar()
        if avg_rating is None:
            return None
        return round(avg_rating, 2)
    
    def stars_representation(self):
        mean_rating = self.mean_rating()
        if mean_rating is None:
            mean_rating = 0
        
        num_full_stars = int(mean_rating)
        num_half_stars = 1 if mean_rating % 1 >= 0.5 else 0
        num_empty_stars = 5 - num_full_stars - num_half_stars

        return "★" * num_full_stars + "½" * num_half_stars + "☆" * num_empty_stars
    
    def num_steps(self):
        return len(self.steps)
    
    @staticmethod
    def filter_by_ingredients(selected_ingredient_ids):
        """
        Filter recipes based on the presence of selected ingredients.

        Parameters:
        - selected_ingredient_ids: List of ingredient IDs to filter by.

        Returns:
        - A list of recipes containing all the selected ingredients.
        """
        if not selected_ingredient_ids:
            return Recipe.query.all()  # Return an empty list if no ingredients are selected

        # Initialize the base query with the first ingredient
        base_query = (
            db.session.query(Recipe)
            .join(QIngredient)
            .filter(QIngredient.ingredient_id == selected_ingredient_ids[0])
        )

        # Create an alias for QIngredient to avoid conflicts in the subsequent joins
        qingredient_alias = aliased(QIngredient)

        # Add additional joins and filters for the rest of the selected ingredients
        for ingredient_id in selected_ingredient_ids[1:]:
            base_query = (
                base_query
                .join(qingredient_alias, Recipe.qIngredients)
                .filter(qingredient_alias.ingredient_id == ingredient_id)
            )

        return base_query.all()

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'))
    user = db.relationship('User', back_populates='bookmarks')
    recipe = db.relationship('Recipe', back_populates='bookmarks')

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'))
    value = db.Column(db.Integer) 
    user = db.relationship('User', back_populates='ratings')
    recipe = db.relationship('Recipe', back_populates='ratings')

class Step(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order = db.Column(db.Integer)
    description = db.Column(db.Text)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'))
    recipe = db.relationship('Recipe', back_populates='steps')

class QIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'))
    quantity = db.Column(db.Integer)
    unit = db.Column(db.String(512))
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'))
    ingredient = db.relationship('Ingredient', back_populates='qIngredients')
    recipe = db.relationship('Recipe', back_populates = 'qIngredients')

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(512))
    qIngredients = db.relationship('QIngredient', back_populates='ingredient')

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    file_extension = db.Column(db.String(8), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'))
    user = db.relationship('User', back_populates='photos')
    recipe = db.relationship('Recipe', back_populates='photos')


class Drink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(512))
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'))
    recipe = db.relationship('Recipe', back_populates = 'drinks')