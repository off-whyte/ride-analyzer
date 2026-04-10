import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip)

export default function EfSparkline({ data }) {
  if (!data || data.length < 2) return null

  const labels = data.map(d => `${d.minute}m`)
  const values = data.map(d => d.ef)

  const chartData = {
    labels,
    datasets: [
      {
        data: values,
        borderColor: '#60a5fa',
        backgroundColor: 'rgba(96, 165, 250, 0.1)',
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
        fill: true,
        tension: 0.3,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: true,
    aspectRatio: 3,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: ctx => ` EF ${ctx.parsed.y.toFixed(3)}`,
        },
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(255,255,255,0.05)' },
        ticks: { color: '#999', font: { size: 11 } },
      },
      y: {
        grid: { color: 'rgba(255,255,255,0.05)' },
        ticks: {
          color: '#999',
          font: { size: 11 },
          callback: v => v.toFixed(2),
        },
      },
    },
  }

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        EF Trend (W/bpm)
      </div>
      <Line data={chartData} options={options} />
    </div>
  )
}
