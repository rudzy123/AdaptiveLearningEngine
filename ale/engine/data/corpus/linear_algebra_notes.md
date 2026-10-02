---
title: Linear Algebra Primer (bundled fixture corpus)
license: MIT - original text written for this repository
---

## Vectors - Intuition
A vector is an ordered list of numbers that describes a quantity with both size and direction, such as a displacement of 3 units east and 2 units north, written (3, 2). Each number is a component. Vectors of the same length can be added by adding matching components, and a vector can be scaled by a single number called a scalar. Geometrically, adding vectors places them tip to tail, and scaling stretches or shrinks the arrow without changing the line it lies on. A negative scalar also flips the arrow.

## Vectors - Definition
Vector addition and scalar multiplication are componentwise. For u = (u1, u2) and v = (v1, v2), u + v = (u1 + v1, u2 + v2), and subtraction works the same way. For a scalar c, c times u is (c times u1, c times u2). The length (magnitude or norm) of u is the square root of the sum of the squared components: |u| = sqrt(u1^2 + u2^2). This is the Pythagorean theorem applied to the components. A vector with length 1 is called a unit vector.

## Vectors - Worked example
Let u = (1, 4) and v = (2, -3) be two vectors. The vector u + v = (3, 1). Scaling gives the vector 2u = (2, 8), so the vector 2u - v = (2 - 2, 8 - (-3)) = (0, 11). For length, take the vector w = (6, 8): the squares of its components are 36 and 64, they sum to 100, and the square root is 10, so the length of w is 10. Do the arithmetic on one vector component at a time and write each intermediate value down.

## Vectors - Common mistakes
Scalar multiplication multiplies every component; it does not add the scalar to each component. Length is not the sum of the components: a vector with components 6 and 8 does not have length 14. Squaring and summing but forgetting the final square root gives the squared length, not the length. When subtracting, distribute the minus sign over every component of the second vector.

## Dot product - Intuition
The dot product turns two vectors into a single number that measures how much they point in the same direction. It is large and positive when the vectors point the same way, zero when they are perpendicular (orthogonal), and negative when they point in roughly opposite directions. The dot product is also where length comes from: a vector dotted with itself gives its squared length.

## Dot product - Definition
For u = (u1, ..., un) and v = (v1, ..., vn) the dot product is u1v1 + u2v2 + ... + unvn: multiply matching components, then add the products. The result is a scalar, not a vector. Geometrically, the dot product equals |u| |v| cos(theta), where theta is the angle between the vectors. Two nonzero vectors are orthogonal exactly when their dot product is zero.

## Dot product - Worked example
Compute the dot product of (2, 3) and (4, -1). The products are 2 times 4 = 8 and 3 times (-1) = -3, and the sum is 5. To find k so that (1, k) and (2, 6) are orthogonal, set 1 times 2 + k times 6 = 0, which gives 6k = -2 and k = -1/3.

## Dot product - Common mistakes
Do not stop after multiplying: listing the componentwise products (8, -3) is not the dot product, which is their sum. Keep track of negative signs when a component is negative, because a dropped sign changes the sum. The dot product of two vectors is a number; if you end with a vector, a step was skipped. To test orthogonality, solve the dot product equals zero as an ordinary equation in the unknown.

## Matrix multiplication - Intuition
Multiplying matrices composes the linear transformations they represent: the product AB means apply B first, then A. Each entry of the product summarizes how one row of A interacts with one column of B. Because of this row-by-column pairing, matrix multiplication is not componentwise, and the order of the factors matters.

## Matrix multiplication - Definition
If A is m by n and B is n by p, the product AB is defined and has size m by p. The entry in row i, column j of AB is the dot product of row i of A with column j of B. The inner dimensions (the n in m by n and n by p) must match; the outer dimensions (m and p) give the shape of the result. If the inner dimensions differ, the product does not exist.

## Matrix multiplication - Worked example
Let A = [[1, 0], [2, 3]] and B = [[4, 1], [5, 2]]. Row 1 of AB: 1 times 4 + 0 times 5 = 4, and 1 times 1 + 0 times 2 = 1. Row 2 of AB: 2 times 4 + 3 times 5 = 23, and 2 times 1 + 3 times 2 = 8. So AB = [[4, 1], [23, 8]]. Reading the entries row by row gives 4, 1, 23, 8.

## Matrix multiplication - Common mistakes
Multiplying matching entries (the elementwise product) is a different operation and does not give AB. Do not pair a row of A with a row of B; always use a column of B. Report the size as rows then columns, so a 2 by 3 matrix times a 3 by 4 matrix gives a 2 by 4 result, not 4 by 2, and the shared 3 disappears. Two 2 by 3 matrices cannot be multiplied because their inner dimensions, 3 and 2, differ.

## Eigenvalues - Intuition
Most vectors change direction when a matrix acts on them, but some special vectors only get stretched or shrunk. These are eigenvectors, and the stretch factor is the eigenvalue. If Av = (lambda)v for a nonzero vector v, then A acts on v as a plain scalar multiple: the direction is preserved (or flipped when lambda is negative) and only the length is scaled.

## Eigenvalues - Definition
A scalar lambda is an eigenvalue of a square matrix A if there is a nonzero vector v with Av = (lambda)v; v is then an eigenvector. Eigenvalues are the roots of the characteristic equation det(A - lambda I) = 0. For a 2 by 2 matrix this reads lambda^2 - (trace)(lambda) + (determinant) = 0, where the trace is the sum of the diagonal entries. The eigenvalues add up to the trace and multiply to the determinant.

## Eigenvalues - Worked example
For a triangular matrix such as A = [[5, 2], [0, 1]], the eigenvalues are the diagonal entries 5 and 1. For a non-triangular matrix such as B = [[3, 1], [1, 3]], the trace is 6 and the determinant is 8, so lambda^2 - 6 lambda + 8 = 0, which factors as (lambda - 2)(lambda - 4) = 0. The eigenvalues are 2 and 4, and indeed 2 + 4 = 6 and 2 times 4 = 8.

## Eigenvalues - Common mistakes
The diagonal entries are the eigenvalues only for triangular (including diagonal) matrices; for a general matrix they are not. The trace and determinant are not themselves eigenvalues: they are the sum and product of them. An eigenvector must be nonzero, because the zero vector satisfies the eigenvalue equation for every lambda. An n by n matrix has n eigenvalues counted with multiplicity, so list all of them, not just one.
