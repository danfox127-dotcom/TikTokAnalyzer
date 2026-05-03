// Mock framer-motion and lucide-react before modules are imported in tests
// Render motion components as plain div wrappers and strip animation props.
const React = require('react');
jest.mock('framer-motion', () => {
  const motion = new Proxy({}, {
    get: () => (props) => {
      const { 
        initial, animate, transition, 
        whileTap, whileHover, whileFocus, whileDrag,
        whileInView, viewport,
        ...rest 
      } = props || {};
      return React.createElement('div', rest, props && props.children);
    },
  });
  return { motion };
});

jest.mock('lucide-react', () => {
  const React = require('react');
  const createIcon = (name) => (props) => React.createElement('svg', { ...props, 'data-icon': name });
  return new Proxy({}, {
    get: (target, prop) => createIcon(prop)
  });
});
