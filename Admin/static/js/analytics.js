const analyticsCtx = document.getElementById("analyticsChart");

if (analyticsCtx) {
    new Chart(analyticsCtx, {
        type: "line",
        data: {
            labels: window.analyticsTrendLabels || ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            datasets: [{
                label: "Average Rating",
                data: window.analyticsTrendValues || [0, 0, 0, 0, 0, 0, 0],
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