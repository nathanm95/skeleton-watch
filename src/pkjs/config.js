module.exports = [
  {
    type: 'heading',
    defaultValue: 'Skeleton Watch'
  },
  {
    type: 'text',
    defaultValue: 'A see-through mechanical movement. Flick your wrist (or tap the screen) to set the balance ticking and the train turning.'
  },
  {
    type: 'section',
    items: [
      { type: 'heading', defaultValue: 'Look' },
      {
        type: 'select',
        messageKey: 'Finish',
        label: 'Finish',
        defaultValue: '0',
        options: [
          { label: 'Classic: gold wheels, rhodium bridges', value: '0' },
          { label: 'Gold', value: '1' },
          { label: 'Steel', value: '2' },
          { label: 'Rose gold', value: '3' },
          { label: 'Black', value: '4' }
        ]
      },
      {
        type: 'select',
        messageKey: 'Hands',
        label: 'Hands',
        defaultValue: '0',
        options: [
          { label: 'Polished white', value: '0' },
          { label: 'Blued steel', value: '1' },
          { label: 'Gold', value: '2' }
        ]
      }
    ]
  },
  {
    type: 'section',
    items: [
      { type: 'heading', defaultValue: 'Motion' },
      {
        type: 'select',
        messageKey: 'Motion',
        label: 'When it ticks',
        defaultValue: '0',
        options: [
          { label: 'On a flick or tap, and briefly each minute', value: '0' },
          { label: 'All the time (uses much more battery)', value: '1' },
          { label: 'Never: one tick a minute', value: '2' }
        ]
      },
      {
        type: 'text',
        defaultValue: 'The small dial at 8 o\'clock is the power reserve: it shows the watch battery.'
      }
    ]
  },
  {
    type: 'submit',
    defaultValue: 'Save'
  }
];
