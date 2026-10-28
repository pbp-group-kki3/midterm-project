# 🌍 Theme: Sustainable Living
## TOPIC: Eco Mindful Living and Food Consumption

### 📖 Application Description
Food production is one of the largest contributors to global environmental impact—agriculture, packaging, and transportation combined account for a significant share of a product's carbon footprint. Yet, this information is almost never visible to consumers at the point of purchase. 

Most people want to make greener choices, but nutrition labels don't show environmental data, and comparing two products' actual impact (ingredients, packaging, emissions) requires research most people don't have time for. As a result, sustainability stays an abstract goal instead of a daily, actionable habit.

**[PRODUCT NAME]** addresses this gap by turning the **Open Food Facts** database into a simple decision-making tool. Instead of asking users to interpret raw data themselves, the platform does the work for them through two core actions:
1. **Comparing** two products side-by-side.
2. **Suggesting** better alternatives to a product they're already considering.

Every comparison and suggestion is backed by real data such as the **Nutri-Score**, **Green-Score** (environmental impact), packaging material and recyclability, and estimated carbon footprint (CO₂e) — pulled directly from the API rather than relying on assumptions or marketing claims.

---

### 🧩 Module List & Assignments
* **Profile** - SERAFIN (2506637136) \
The profile module manages user accounts and personal preferences. Users can register, log in, edit their profile, and securely access their saved information. They can also specify dietary preferences, allergies, and nutritional goals, which may be used to personalized meal plans and product recommendations.

* **Product Discovery** - BECCA (2506637110) \
The Main module acts as the primary product-discovery page. Users can search for a food product by name and view a concise summary of its nutritional and environmental information. identifies similar products from the same category and recommends potentially healthier or more environmentally friendly alternatives. Each recommendation includes an explanation of why it may be a better choice.

* **Meal Plan** - REYHAN (2506637086) \
The Personalized Meal Plan module generates meal recommendations based on the user’s dietary preferences, allergies, nutritional goals, and selected planning period. It provides suitable recipes for each meal and allows users to replace recommendations that they do not prefer.

* **Product Comparison** - ALYSSA (2506558466) \
The Product Comparison module allows users to select two or three products and evaluate them side by side. Products are compared using consistent criteria, including nutritional quality, environmental score, ingredients, and packaging. When sufficient data is available, it may also estimate the potential impact of regularly choosing one product over another.

* **Food of The Day** - ARYAN (2506636985) \
The Food of the Day module introduces users to a selected sustainable food, ingredient, recipe, or product each day. The recommendation may be based on nutritional value, environmental performance, seasonal relevance, or educational value. Users can interact with the daily recommendation by reading its sustainability information, leaving comments, and viewing opinions shared by other community members.

* **Blog** - QEELA \
The Blog module provides educational content about sustainable food consumption and environmentally responsible lifestyles. It helps users understand the information presented elsewhere in the application and encourages them to develop more sustainable daily habits. Articles may discuss food waste, packaging, recycling, carbon footprints, sustainable shopping, nutrition labels, seasonal food, and responsible consumption.

---

### 🔗 API Integration
* **Open Food Facts** - [https://id.openfoodfacts.org/](https://id.openfoodfacts.org/)



### DEV NOTES:

* **SERAFIN** - (2506637136) \
Due to a misunderstanding on my part, commit convention will be adhered to from 28th of October 2026 onwards, all prior commits will remain as they are for stability and safety's sake. Below will be the original commits and more convention counterpart.

| Original Commit Hash & Message | Conventional Commit Counterpart |
| :--- | :--- |
| `298c3b0c9ab55f6b381823fff073836237c4f15d`<br>testing git quickly | `test(main): testing git` |
| `b9b63eddb77b19937476a0d8288736e6bbadb1dd`<br>Initial Profile Setup | `chore/feat(profiles): initial setup and framework` |
| `0b95267dc14d4d1a21b9db8b0ffb007f2663f486`<br>Append to prior commit | `chore(profiles): committing files that were left out` |
| `f0cab38a052ab1d410f109ad6f4b6d3835e2c4d1`<br>Initial Profile Model | `feat(profiles): added profiles model` |
| `29c2a3fca3fb1a272f88714691705335ae119c7d`<br>Profiles view | `feat(profiles): added profiles view` |
| `328e28a861aced4254a043e709d68ae1c8f5b73a`<br>Forgot to stage again this is for prior commit | `chore(profiles) commiting files that were left out` |
| `ab956a8c1d62dd8542816bb87d6f818c83c08335`<br>Register view and HTMLs set up and created | `feat(profiles) added register html and view` |
| `9fe9843e696dce7b9715dd614c006fe0c6f7b09e`<br>PROFILE SPEEDRUN | `feat/refactor(profiles): added login system and profile html, refactored the code to be cleaner and better fit the requirements` |
| `690e61eb30ac58af9ee072c414cf5f12933edbf5`<br>APPEND | `chore(profiles): commiting files that were left out` |