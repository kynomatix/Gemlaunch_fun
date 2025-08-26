const express = require('express');
const path = require('path');

const app = express();
const port = process.env.PORT || 5000;

// Set view engine to EJS but use .html files
app.set('view engine', 'html');
app.engine('html', require('ejs').renderFile);
app.set('views', path.join(__dirname, 'templates'));

// Serve static files
app.use('/static', express.static(path.join(__dirname, 'static')));

// Routes (exactly matching Flask routes)
app.get('/', (req, res) => {
    res.render('index');
});

app.get('/docs', (req, res) => {
    res.render('docs');
});

app.get('/pitch-deck', (req, res) => {
    res.render('pitch-deck');
});

app.get('/health', (req, res) => {
    res.json({ status: 'healthy' });
});

// Start server
app.listen(port, '0.0.0.0', () => {
    console.log(`Server running on port ${port}`);
});