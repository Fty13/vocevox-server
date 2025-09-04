from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from reading import mecab

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        text = request.form['text']
        use_ruby = 'use_ruby_tags' in request.form
        processed_text = mecab.reading(text, useRubyTags=use_ruby)
        return render_template('index.html', processed_text=processed_text, text=text, use_ruby_tags=use_ruby)
    return render_template('index.html', processed_text='', text='', use_ruby_tags=False)

@app.route('/api/furigana', methods=['POST'])
def api_furigana():
    data = request.get_json()
    text = data.get('text', '')
    use_ruby = data.get('useRubyTags', False)
    processed_text = mecab.reading(text, useRubyTags=use_ruby)
    return jsonify({'furigana': processed_text})

if __name__ == '__main__':
    app.run(debug=True)
