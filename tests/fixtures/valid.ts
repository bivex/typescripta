import { readFileSync } from "fs";

interface User {
    id: number;
    name: string;
}

class UserImpl implements User {
    constructor(public id: number, public name: string) {}

    rename(newName: string): void {
        this.name = newName;
    }
}

namespace UserUtils {
    export function greeting(user: User): string {
        return "Hello";
    }
}

function makeUser(): User {
    return new UserImpl(1, "Ana");
}

const greet = (name: string): string => `Hello, ${name}`;
