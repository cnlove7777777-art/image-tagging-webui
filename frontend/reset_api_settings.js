// Simple script to reset API settings in localStorage
// This will clear any custom API URLs that might be causing connection issues
localStorage.removeItem('apiBaseUrl');
localStorage.removeItem('ldb_api_settings');
localStorage.removeItem('appSettings');

console.log('API settings reset complete!');
console.log('Base URL will now use default: /api');
