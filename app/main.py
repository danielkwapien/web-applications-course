import datetime
import dateutil.tz
import xhtml2pdf
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, make_response
from . import db, bcrypt
from . import model
import flask_login
from flask_login import current_user
from .forms import RecipeForm, StepForm, IngredientForm, DrinkForm
from flask_wtf import FlaskForm
import pathlib
from flask import current_app
from sqlalchemy import desc, or_, and_
from werkzeug.utils import secure_filename

bp = Blueprint("main", __name__)

@bp.route("/")
def index():

    query = db.select(model.Recipe).order_by(model.Recipe.id.desc())
    recipes = db.session.execute(query).scalars().all()
    
    return render_template("main/index.html", recipes = recipes)

@bp.route("/search", methods= ['GET'])
def search():
    results = []
        # Execute the query
    query= db.select(model.Ingredient)
    all_ingredients = db.session.execute(query).scalars().all()
    return render_template('search/search.html', results=results, all_ingredients= all_ingredients)

@bp.route("/search/new-search", methods= ['GET'])
def new_search():
    q = request.args.get('q')
    selected_ingredient_ids = request.args.getlist('i')
    print(selected_ingredient_ids)

    # Filter recipes based on search query
    if q != '':
        query = (
            db.select(model.Recipe)
            .where(
                or_(
                    model.Recipe.title.ilike(f"%{q}%"),
                    model.Recipe.description.ilike(f"%{q}%")
                )
            )
        )
        text_search_results = db.session.execute(query).scalars().all()

    elif selected_ingredient_ids:
        text_search_results = model.Recipe.query.all()
    else:
        text_search_results = []
    ingredient_filter_results = model.Recipe.filter_by_ingredients(selected_ingredient_ids)
    results = list(set(text_search_results) & set(ingredient_filter_results))

    return render_template('search/search_results.html', results=results)

@bp.route("/search/new-search-ingredient", methods=['GET'])
def new_search_ingredient():
    selected_ingredient_ids = request.args.getlist('i')
    print(selected_ingredient_ids)
    filtered_recipes = model.Recipe.filter_by_ingredients(selected_ingredient_ids)
    return render_template('search/search_results.html', results=filtered_recipes)
    
@bp.route("/recipe/<int:recipe_id>")
def recipe(recipe_id):
    query = db.select(model.Recipe).where(model.Recipe.id == recipe_id)
    recipe = db.session.execute(query).scalar_one()
    number_steps = len(recipe.steps)
    if len(recipe.drinks) > 0:
        drinks = recipe.drinks
    else:
        drinks = None
    photos = []
    for photo in recipe.photos:
        if photo.user != recipe.user:
            photos.append(photo)
    if len(photos)== 0:
        photos = None

    if current_user.is_authenticated:
        query = db.select(model.Rating).where(model.Rating.user == current_user).where(model.Rating.recipe_id == recipe_id)
        rating = db.session.execute(query).scalar_one_or_none()
        if rating is None:
            rating_button = 'non-rated'
            rating_value = None
        else:
            rating_button= 'rated'
            rating_value = rating.value

        query = db.select(model.Bookmark).where(model.Bookmark.recipe_id == recipe_id).where(model.Bookmark.user ==current_user)
        bookmark= db.session.execute(query).scalar_one_or_none()
        if bookmark is None:
            bookmark_button = 'not-saved'
        else:
            bookmark_button = 'saved'
    else:
        return render_template('recipe/recipe.html', recipe=recipe, rating_button = 'non-rated',
        rating_value = None, bookmark_button= 'not-saved', number_steps= number_steps, drinks = drinks, photos = photos)
    
    return render_template('recipe/recipe.html', recipe=recipe, rating_button = rating_button,
    rating_value = rating_value, bookmark_button= bookmark_button, number_steps= number_steps, drinks = drinks, photos = photos)

@bp.route('/recipes_with_ingredient/<ingredient_name>')
def recipes_with_ingredient(ingredient_name):
    filtered_recipes = model.Recipe.filter_by_ingredient(ingredient_name)
    return render_template('main/index.html', recipes=filtered_recipes)


# New route to generate and download the PDF
@bp.route('/recipe/download_pdf/<int:recipe_id>')
def download_pdf(recipe_id):
    query = db.select(model.Recipe).where(model.Recipe.id == recipe_id)
    recipe = db.session.execute(query).scalar_one()
    query = db.select(model.Photo).where(
        and_(
            model.Photo.recipe_id == recipe_id,
            model.Photo.user_id == recipe.user_id
        )
    )    
    photos = db.session.execute(query).scalars().all()
    for photo in photos:
        print(photo.id, photo.file_extension)
    number_steps = len(recipe.steps)

    # Render the recipe template to get the HTML content
    html_content = render_template('recipe/recipe_pdf.html', recipe=recipe, rating_button = 'non-rated',
        rating_value = None, bookmark_button= 'not-saved', photos= photos, number_steps= number_steps)
    

    # Create a PDF response
    response = make_response(pdf_from_html(html_content))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=recipe.pdf'

    return response

def pdf_from_html(html_content):
    from io import BytesIO
    from xhtml2pdf import pisa

    # Create a PDF using pisa
    pdf_data = BytesIO()
    pisa.CreatePDF(BytesIO(html_content.encode('utf-8')), dest=pdf_data)

    # Reset the BytesIO object for reading
    pdf_data.seek(0)

    return pdf_data.read()



@bp.route('/user/<int:user_id>', methods= ['GET'])
def user(user_id):
    
    query = db.select(model.User).where(model.User.id == user_id)
    user= db.session.execute(query).scalar_one()
    number_recipes = len(user.recipes)
    number_photos = len(user.photos)
    return render_template('user/user.html', user = user, number_recipes = number_recipes, number_photos= number_photos)

#  initializes a new instance of the RecipeForm, which is then passed to the template for rendering
@bp.route('/recipe_creation', methods = ['GET', 'POST'])
@flask_login.login_required
def recipe_creation():
    form = RecipeForm() 
    return render_template('recipe_creation/recipe_creation.html', form= form)
        
@bp.route('/recipe_creation/post', methods= ['POST'])
@flask_login.login_required
def recipe_creation_post():
    form = RecipeForm()
    #import pdb; pdb.set_trace()

    # if the form data passes validation -> extract the data
    if form.validate_on_submit():
        title = form.title.data
        description = form.description.data
        cooking_time= form.cooking_time.data
        user_id = current_user.id
        print(user_id)

        # Creating and Adding Recipe to the Database using the extracted data
        recipe = model.Recipe(title=title.capitalize(), user_id=user_id, description=description, cooking_time=cooking_time) #assume description is well written
        db.session.add(recipe)
        
        #For each step in the form data, a Step object is created and associated with the recipe.
        for step in form.steps.data:
            step = model.Step(order = step['order'], description = step['description'].capitalize(), recipe = recipe) #assume no dots
            db.session.add(step)

        # For each ingredient in the form data, a query is made to check if the ingredient already exists. If not, a new Ingredient object is created. 
        # A QIngredient object is then created and associated with the recipe.
        for ingred in form.ingredients.data:
            query_ingred = db.select(model.Ingredient).where(model.Ingredient.name == ingred['name'].lower())
            ingredient = db.session.execute(query_ingred).scalar_one_or_none()
            
            if ingredient is None:
                ingredient = model.Ingredient(name = ingred['name'].lower())
                db.session.add(ingredient)

            qingred = model.QIngredient(quantity= ingred['quantity'], ingredient = ingredient, unit= ingred['unit'].lower(), recipe = recipe)
            db.session.add(qingred)

        # Check if drinks are provided, as it is NOT MANDATORY
        if form.drinks:
            print(form.drinks)
            for drink in form.drinks.data:
                query_drink = db.select(model.Drink).where(model.Drink.name == drink['name'].lower())
                existing_drink = db.session.execute(query_drink).scalar_one_or_none()

                if existing_drink  is None:
                    new_drink = model.Drink(name=drink['name'].lower(), recipe = recipe)
                    db.session.add(new_drink)
            



        # For each photo in the form data, a Photo object is created and associated with the recipe. The photo file is saved to the server.
        photos = request.files.getlist("photos")
        print(photos)
        for photo in photos:
            print(photo)
            content_type = photo.content_type
            print(content_type)
            filename = secure_filename(photo.filename)
            if filename != '':
                if content_type == "image/png":
                    file_extension = "png"
                elif content_type == "image/jpeg":
                    file_extension = "jpg"
                else:
                    abort(400, f"Unsupported file type {content_type}")
                    
                photo_obj = model.Photo(
                    recipe=recipe,
                    file_extension=file_extension,
                    user_id = current_user.id
                )
                db.session.add(photo_obj)
                db.session.commit()

                path = (
                    pathlib.Path(current_app.root_path)
                    / "static"
                    / "photos"
                    / f"photo-{photo_obj.id}.{file_extension}"
                )
                photo.save(path)
            

        db.session.commit()
        # The user is redirected to the page displaying the newly created recipe.
        return redirect(url_for('main.recipe', recipe_id = recipe.id))

    else:
        print('Not validated!')
        print(form.errors)
    return redirect(url_for('main.index'))

@bp.route('/create/stepAddEntry', methods=['POST', 'GET'])
def recipeStepAddEntry():
    # Initializes a RecipeForm instance using the data from the request form
    form = RecipeForm(request.form)
    new_entry = StepForm()
    new_entry.order.data = len(form.steps.entries)+1
    form.steps.append_entry(new_entry.data)
    # Renders the 'steps_template.html' template, passing the form with the newly added step entry.
    rendered_template = render_template('recipe_creation/steps_template.html', form=form)
    return jsonify(html=rendered_template)
    

@bp.route('/create/igredientAddEntry', methods=['POST', 'GET'])
def recipeIngredientAddEntry():
    form = RecipeForm(request.form)
    form.ingredients.append_entry(IngredientForm().data)
    rendered_template = render_template('recipe_creation/ingredients_template.html', form=form)
    return jsonify(html=rendered_template)

@bp.route('/create/drinkAddEntry', methods=['POST', 'GET'])
def recipeDrinkAddEntry():
    form = RecipeForm(request.form)
    form.drinks.append_entry(DrinkForm().data)
    if not form.drinks:
        form.drinks.append_entry()
    rendered_template = render_template('recipe_creation/drinks_template.html', form=form)
    return jsonify(html=rendered_template)
 

@bp.route('/addRating/<int:recipe_id>', methods= ['POST'])
@flask_login.login_required
def rating_post(recipe_id):
    #recipe_id = request.form.get('recipe_id')
    value = request.form.get('rating')
    query = db.select(model.Rating).where(model.Rating.user == current_user).where(model.Rating.recipe_id == recipe_id)
    rating = db.session.execute(query).scalar_one_or_none()
    if rating is None:
        rating = model.Rating(user_id = current_user.id, recipe_id = recipe_id, value = value)
        db.session.add(rating)
    else:
        rating.value = value
    db.session.commit()
    return redirect(url_for('main.recipe', recipe_id = recipe_id))
    


@bp.route('/addPhoto/<int:recipe_id>', methods= ['POST'])
@flask_login.login_required
def photo_post(recipe_id):
    uploaded_file = request.files['photo']
    if uploaded_file.filename != '':
        content_type = uploaded_file.content_type
        if content_type == "image/png":
            file_extension = "png"
        elif content_type == "image/jpeg":
            file_extension = "jpg"
        else:
            abort(400, f"Unsupported file type {content_type}")
        
        query = db.select(model.Recipe).where(model.Recipe.id == recipe_id)
        recipe = db.session.execute(query).scalar_one()
        photo_obj = model.Photo(
            recipe=recipe,
            file_extension=file_extension,
            user_id = current_user.id
        )
        db.session.add(photo_obj)
        db.session.commit()

        path = (
            pathlib.Path(current_app.root_path)
            / "static"
            / "photos"
            / f"photo-{photo_obj.id}.{file_extension}"
        )
        uploaded_file.save(path)
    return redirect(url_for('main.recipe', recipe_id = recipe_id))


@bp.route('/saveBookmark/<int:recipe_id>', methods = ['POST'])
@flask_login.login_required
def bookmark(recipe_id):
    query = db.select(model.Bookmark).where(model.Bookmark.recipe_id == recipe_id).where(model.Bookmark.user_id ==current_user.id)
    bookmark= db.session.execute(query).scalar_one_or_none()
    if bookmark is None:
        bookmark= model.Bookmark(user_id = current_user.id, recipe_id = recipe_id)
        db.session.add(bookmark)

    db.session.commit()
    return redirect(url_for('main.recipe', recipe_id = recipe_id))

@bp.route('/deleteBookmark/<int:recipe_id>', methods = ['POST'])
@flask_login.login_required
def remove_bookmark(recipe_id):
    query = db.select(model.Bookmark).where(model.Bookmark.recipe_id == recipe_id).where(model.Bookmark.user_id ==current_user.id)
    bookmark= db.session.execute(query).scalar_one()
    if bookmark:
        db.session.delete(bookmark)
        db.session.commit()
    return redirect(url_for('main.recipe', recipe_id = recipe_id))
