const ctx = document.getElementById('chart');

if (ctx) {
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: window.chartLabels || ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            datasets: [{
                label: 'Average Rating',
                data: window.chartValues || [0, 0, 0, 0, 0, 0, 0],
                borderWidth: 2,
                tension: 0.35,
                fill: false
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: true
                }
            },
            scales: {
                y: {
                    min: 0,
                    max: 5,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}