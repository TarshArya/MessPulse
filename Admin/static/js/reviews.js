const donutCtx = document.getElementById("donutChart");
if (donutCtx) {
    new Chart(donutCtx, {
        type: "doughnut",
        data: {
            labels: window.issueLabels || ["No Issues Yet"],
            datasets: [{
                data: window.issueValues || [1],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: "bottom"
                }
            }
        }
    });
}

const lineCtx = document.getElementById("lineChart");
if (lineCtx) {
    new Chart(lineCtx, {
        type: "line",
        data: {
            labels: window.reviewTrendLabels || ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            datasets: [{
                label: "Review Count",
                data: window.reviewTrendValues || [0, 0, 0, 0, 0, 0, 0],
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
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}