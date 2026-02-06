export default function Card({ color, value, size = 'normal' }) {
  const sizeClass = size === 'large' ? 'current-card' : ''
  
  return (
    <div className={`card ${color} ${sizeClass}`}>
      {value}
    </div>
  )
}
