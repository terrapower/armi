const path = require('path');

module.exports = {
  entry: './src/grid_gui_lib.js',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
    library: 'bundle'
  },
  mode: 'development'
};
