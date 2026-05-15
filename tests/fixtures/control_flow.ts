function score(values: number[]): number {
    let total = 0;

    for (const value of values) {
        if (value > 0) {
            total = total + value;
        } else {
            continue;
        }
    }

    while (total > 100) {
        total = total - 10;
    }

    do {
        total = total - 1;
    } while (total > 50);

    switch (total) {
        case 0:
            return 0;
        case 1:
            return 1;
        default:
            return total;
    }
}

class MathBox {
    normalize(input: number): number {
        if (input < 0) {
            return 0;
        }

        try {
            return input;
        } catch (e) {
            return 0;
        }
    }
}
