# PHP Code Refactoring Examples

This document provides real-world examples of code improvements, showing common issues and their solutions. This is merely a logical example, and the actual implementation should be determined based on the user's code framework.

## Example 1: Long Method with Deep Nesting

### ❌ Before

```php
function processUserData($userId, $data) {
    if ($userId) {
        $user = User::find($userId);
        if ($user) {
            if ($user->isActive()) {
                if ($data) {
                    if (isset($data['email'])) {
                        $user->email = $data['email'];
                    }
                    if (isset($data['name'])) {
                        $user->name = $data['name'];
                    }
                    if ($user->save()) {
                        return true;
                    } else {
                        return false;
                    }
                }
            }
        }
    }
    return false;
}
```

**Issues**:
- Deep nesting (5 levels)
- Multiple return points
- No input validation
- No error messages
- God function doing everything

### ✅ After

```php
function processUserData(int $userId, array $data): bool {
    $user = $this->findAndValidateUser($userId);
    if (!$user) {
        return false;
    }

    $this->updateUserData($user, $data);
    return $user->save();
}

private function findAndValidateUser(int $userId): ?User {
    if ($userId <= 0) {
        $this->logError('Invalid user ID', ['userId' => $userId]);
        return null;
    }

    $user = User::find($userId);
    if (!$user) {
        $this->logError('User not found', ['userId' => $userId]);
        return null;
    }

    if (!$user->isActive()) {
        $this->logError('User is inactive', ['userId' => $userId]);
        return null;
    }

    return $user;
}

private function updateUserData(User $user, array $data): void {
    if (isset($data['email'])) {
        $user->email = $this->validateEmail($data['email']);
    }

    if (isset($data['name'])) {
        $user->name = $this->sanitizeString($data['name']);
    }
}

private function validateEmail(string $email): string {
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        throw new InvalidArgumentException("Invalid email format: {$email}");
    }
    return $email;
}

private function sanitizeString(string $input): string {
    return htmlspecialchars(strip_tags(trim($input)), ENT_QUOTES, 'UTF-8');
}
```

**Improvements**:
- Single Responsibility Principle
- Early returns reduce nesting
- Proper type hints
- Input validation
- Error logging
- Extracted methods

---

## Example 2: SQL Injection Vulnerability

### ❌ Before

```php
function getUserByEmail($email) {
    $query = "SELECT * FROM users WHERE email = '" . $_GET['email'] . "'";
    $result = mysql_query($query);
    return mysql_fetch_assoc($result);
}

function updateUser($id, $data) {
    $sql = "UPDATE users SET
            name = '{$data['name']}',
            email = '{$data['email']}',
            status = '{$data['status']}'
            WHERE id = {$id}";
    return $this->db->query($sql);
}
```

**Critical Issues**:
- Direct string concatenation
- No prepared statements
- SQL injection vulnerabilities
- Deprecated mysql_* functions
- No input validation

### ✅ After

```php
function getUserByEmail(string $email): ?User {
    $this->validateEmail($email);

    $stmt = $this->db->prepare(
        "SELECT id, name, email, status, created_at
         FROM users
         WHERE email = :email
         LIMIT 1"
    );

    $stmt->bindParam(':email', $email, PDO::PARAM_STR);
    $stmt->execute();

    $result = $stmt->fetch(PDO::FETCH_ASSOC);

    return $result ? new User($result) : null;
}

function updateUser(int $id, array $data): bool {
    $this->validateUserId($id);
    $this->validateUserData($data);

    $stmt = $this->db->prepare(
        "UPDATE users
         SET name = :name,
             email = :email,
             status = :status,
             updated_at = NOW()
         WHERE id = :id"
    );

    $stmt->bindParam(':id', $id, PDO::PARAM_INT);
    $stmt->bindParam(':name', $data['name'], PDO::PARAM_STR);
    $stmt->bindParam(':email', $data['email'], PDO::PARAM_STR);
    $stmt->bindParam(':status', $data['status'], PDO::PARAM_STR);

    return $stmt->execute();
}

private function validateUserId(int $id): void {
    if ($id <= 0) {
        throw new InvalidArgumentException('Invalid user ID');
    }
}

private function validateUserData(array $data): void {
    if (empty($data['name']) || empty($data['email'])) {
        throw new InvalidArgumentException('Name and email are required');
    }

    if (!filter_var($data['email'], FILTER_VALIDATE_EMAIL)) {
        throw new InvalidArgumentException('Invalid email format');
    }

    if (!in_array($data['status'], ['active', 'inactive', 'suspended'])) {
        throw new InvalidArgumentException('Invalid user status');
    }
}
```

**Improvements**:
- Prepared statements prevent SQL injection
- Type safety with PDO::PARAM_* constants
- Input validation before queries
- Specific field selection instead of SELECT *
- Proper error handling
- Named parameters for readability

---

## Example 3: N+1 Query Problem

### ❌ Before

```php
function getUsersWithPosts() {
    $users = User::all();

    foreach ($users as $user) {
        // This triggers a query for EACH user (N+1 problem)
        $user->posts;
    }

    return $users;
}

// Or worse:
function displayUserPosts() {
    $users = DB::select("SELECT * FROM users");

    foreach ($users as $user) {
        $posts = DB::select(
            "SELECT * FROM posts WHERE user_id = {$user->id}"
        );

        echo "{$user->name}: " . count($posts) . " posts\n";
    }
}
```

**Performance Issues**:
- N+1 query problem (1 query for users + N queries for posts)
- No eager loading
- Inefficient database usage

### ✅ After

```php
function getUsersWithPosts(): Collection {
    // Single query with JOIN - eager loading
    return User::with('posts')
        ->whereHas('posts')
        ->get();
}

// Or with raw SQL:
function displayUserPosts(): array {
    $results = DB::select(
        "SELECT
            u.id,
            u.name,
            COUNT(p.id) as post_count
         FROM users u
         INNER JOIN posts p ON u.id = p.user_id
         GROUP BY u.id, u.name
         ORDER BY post_count DESC"
    );

    return $results;
}

// Or with pagination for large datasets:
function getUsersWithPostsPaginated(int $perPage = 20): LengthAwarePaginator {
    return User::with('posts')
        ->where('status', 'active')
        ->orderBy('created_at', 'desc')
        ->paginate($perPage);
}
```

**Improvements**:
- Eager loading eliminates N+1 problem
- Single query with JOIN
- Pagination for large datasets
- Proper indexing on foreign keys

---

## Example 4: Magic Numbers and Hardcoded Values

### ❌ Before

```php
function calculateDiscount($amount) {
    if ($amount > 100) {
        return $amount * 0.1;
    } elseif ($amount > 500) {
        return $amount * 0.15;
    } elseif ($amount > 1000) {
        return $amount * 0.2;
    }
    return 0;
}

function getStatus($code) {
    if ($code == 1) {
        return 'active';
    } elseif ($code == 2) {
        return 'inactive';
    } elseif ($code == 3) {
        return 'suspended';
    }
}

function retry($attempt) {
    if ($attempt > 3) {
        throw new Exception('Too many attempts');
    }
    // retry logic
    sleep(5);
}
```

**Issues**:
- Magic numbers scattered throughout
- Hardcoded business logic
- No constants
- Difficult to maintain

### ✅ After

```php
class DiscountCalculator {
    private const TIER_1_THRESHOLD = 100;
    private const TIER_2_THRESHOLD = 500;
    private const TIER_3_THRESHOLD = 1000;

    private const TIER_1_RATE = 0.10;  // 10%
    private const TIER_2_RATE = 0.15;  // 15%
    private const TIER_3_RATE = 0.20;  // 20%

    public function calculateDiscount(float $amount): float {
        if ($amount > self::TIER_3_THRESHOLD) {
            return $amount * self::TIER_3_RATE;
        }

        if ($amount > self::TIER_2_THRESHOLD) {
            return $amount * self::TIER_2_RATE;
        }

        if ($amount > self::TIER_1_THRESHOLD) {
            return $amount * self::TIER_1_RATE;
        }

        return 0.0;
    }
}

class UserStatus {
    public const ACTIVE = 1;
    public const INACTIVE = 2;
    public const SUSPENDED = 3;

    private const STATUS_MAP = [
        self::ACTIVE => 'active',
        self::INACTIVE => 'inactive',
        self::SUSPENDED => 'suspended',
    ];

    public static function toString(int $code): string {
        if (!isset(self::STATUS_MAP[$code])) {
            throw new InvalidArgumentException("Invalid status code: {$code}");
        }

        return self::STATUS_MAP[$code];
    }

    public static function fromString(string $status): int {
        $code = array_search($status, self::STATUS_MAP);
        if ($code === false) {
            throw new InvalidArgumentException("Invalid status: {$status}");
        }
        return $code;
    }
}

class RetryService {
    private const MAX_ATTEMPTS = 3;
    private const RETRY_DELAY_SECONDS = 5;

    public function executeWithRetry(int $attempt = 1): void {
        if ($attempt > self::MAX_ATTEMPTS) {
            throw new RuntimeException(
                'Maximum retry attempts exceeded: ' . self::MAX_ATTEMPTS
            );
        }

        try {
            $this->executeOperation();
        } catch (Exception $e) {
            $this->logRetry($attempt, $e);
            sleep(self::RETRY_DELAY_SECONDS);
            $this->executeWithRetry($attempt + 1);
        }
    }

    private function executeOperation(): void {
        // Business logic here
    }

    private function logRetry(int $attempt, Exception $e): void {
        error_log("Attempt {$attempt} failed: {$e->getMessage()}");
    }
}
```

**Improvements**:
- Named constants with clear meaning
- Business logic separated into classes
- Type safety
- Better error handling
- Easy to modify thresholds
- Self-documenting code

---

## Example 5: God Class (Too Many Responsibilities)

### ❌ Before

```php
class UserManager {
    public function createUser($data) { /* ... */ }
    public function updateUser($id, $data) { /* ... */ }
    public function deleteUser($id) { /* ... */ }
    public function sendEmail($user, $subject, $body) { /* ... */ }
    public function validatePassword($password) { /* ... */ }
    public function hashPassword($password) { /* ... */ }
    public function login($email, $password) { /* ... */ }
    public function logout() { /* ... */ }
    public function generateToken() { /* ... */ }
    public function validateToken($token) { /* ... */ }
    public function exportToCSV($users) { /* ... */ }
    public function importFromCSV($file) { /* ... */ }
    public function sendNotification($user, $message) { /* ... */ }
    public function uploadAvatar($file) { /* ... */ }
    public function deleteAvatar($user) { /* ... */ }
}
```

**Issues**:
- God class (violates SRP)
- Too many responsibilities
- Hard to test
- Hard to maintain
- Low cohesion

### ✅ After

```php
// Separate classes for each responsibility

class UserService {
    public function __construct(
        private UserRepository $repository,
        private PasswordService $passwordService,
        private UserValidator $validator
    ) {}

    public function create(array $data): User {
        $this->validator->validate($data);
        $hashedPassword = $this->passwordService->hash($data['password']);

        $user = new User([
            'name' => $data['name'],
            'email' => $data['email'],
            'password' => $hashedPassword,
        ]);

        return $this->repository->save($user);
    }

    public function update(int $userId, array $data): User {
        $user = $this->repository->find($userId);
        if (!$user) {
            throw new UserNotFoundException($userId);
        }

        $user->fill($data);
        return $this->repository->save($user);
    }

    public function delete(int $userId): bool {
        return $this->repository->delete($userId);
    }
}

class AuthService {
    public function __construct(
        private UserService $userService,
        private TokenService $tokenService,
        private SessionService $sessionService
    ) {}

    public function login(string $email, string $password): string {
        $user = $this->userService->findByEmail($email);
        if (!$user) {
            throw new AuthenticationException('Invalid credentials');
        }

        if (!$this->userService->verifyPassword($password, $user->password)) {
            throw new AuthenticationException('Invalid credentials');
        }

        $token = $this->tokenService->generate($user);
        $this->sessionService->set('user_id', $user->id);

        return $token;
    }

    public function logout(): void {
        $this->sessionService->clear();
    }
}

class EmailService {
    public function __construct(
        private MailerInterface $mailer
    ) {}

    public function sendUserEmail(User $user, string $subject, string $body): void {
        $email = (new Email())
            ->from('noreply@example.com')
            ->to($user->email)
            ->subject($subject)
            ->html($body);

        $this->mailer->send($email);
    }
}

class NotificationService {
    public function __construct(
        private EmailService $emailService,
        private SmsService $smsService
    ) {}

    public function sendNotification(User $user, string $message): void {
        $this->emailService->sendUserEmail($user, 'Notification', $message);

        if ($user->smsEnabled) {
            $this->smsService->send($user->phone, $message);
        }
    }
}

class FileService {
    public function __construct(
        private StorageInterface $storage,
        private ImageValidator $validator
    ) {}

    public function uploadAvatar(UploadedFile $file, User $user): string {
        $this->validator->validateImage($file);

        $filename = $this->generateFilename($file, $user->id);
        $path = "avatars/{$filename}";

        $this->storage->put($path, file_get_contents($file));

        return $path;
    }

    public function deleteAvatar(User $user): void {
        if ($user->avatar) {
            $this->storage->delete($user->avatar);
        }
    }

    private function generateFilename(UploadedFile $file, int $userId): string {
        return "{$userId}_avatar_" . time() . '.' . $file->getClientOriginalExtension();
    }
}

class UserExportService {
    public function exportToCSV(Collection $users): string {
        $headers = ['ID', 'Name', 'Email', 'Status', 'Created At'];
        $rows = $users->map(fn($user) => [
            $user->id,
            $user->name,
            $user->email,
            $user->status,
            $user->created_at->format('Y-m-d H:i:s'),
        ]);

        $fp = fopen('php://temp', 'r+');
        fputcsv($fp, $headers);
        foreach ($rows as $row) {
            fputcsv($fp, $row);
        }
        rewind($fp);

        $csv = stream_get_contents($fp);
        fclose($fp);

        return $csv;
    }
}
```

**Improvements**:
- Single Responsibility Principle
- Dependency Injection
- Easier to test each class
- Better code organization
- Higher cohesion
- Lower coupling

---

## Example 6: Error Handling Improvements

### ❌ Before

```php
function processPayment($userId, $amount) {
    $user = User::find($userId);
    $payment = new Payment();
    $payment->user_id = $user->id;
    $payment->amount = $amount;

    if ($payment->save()) {
        return true;
    } else {
        return false;
    }
}

function divide($a, $b) {
    return $a / $b;
}
```

**Issues**:
- No error handling
- Silent failures
- No validation
- Division by zero risk

### ✅ After

```php
function processPayment(int $userId, float $amount): Payment {
    try {
        $user = $this->findUser($userId);
        $this->validatePaymentAmount($amount);
        $this->checkUserEligibility($user);

        $payment = $this->createPayment($user, $amount);
        $this->processTransaction($payment);

        return $payment;

    } catch (UserNotFoundException $e) {
        $this->logError('User not found', ['userId' => $userId]);
        throw $e;

    } catch (InvalidPaymentException $e) {
        $this->logError('Invalid payment amount', ['amount' => $amount]);
        throw $e;

    } catch (PaymentProcessingException $e) {
        $this->logError('Payment processing failed', [
            'userId' => $userId,
            'amount' => $amount,
            'error' => $e->getMessage()
        ]);
        throw $e;

    } catch (Exception $e) {
        $this->logError('Unexpected payment error', [
            'userId' => $userId,
            'error' => $e->getMessage()
        ]);
        throw new PaymentProcessingException('Payment failed', 0, $e);
    }
}

function divide(float $a, float $b): float {
    if ($b === 0.0) {
        throw new InvalidArgumentException('Division by zero is not allowed');
    }

    return $a / $b;
}
```

**Improvements**:
- Specific exception types
- Proper error logging
- Input validation
- Clear error messages
- Exception chaining
- Type safety

---

## Key Refactoring Principles

1. **Extract Method**: Break down long methods into smaller, focused ones
2. **Single Responsibility**: Each class/method should have one reason to change
3. **DRY (Don't Repeat Yourself)**: Eliminate duplicate code
4. **Early Returns**: Reduce nesting by returning early
5. **Named Constants**: Replace magic numbers with named constants
6. **Type Safety**: Use type hints and return types
7. **Input Validation**: Validate all inputs at the beginning
8. **Error Handling**: Use exceptions instead of returning false/null
9. **Dependency Injection**: Inject dependencies instead of creating them
10. **Composition over Inheritance**: Favor composition for flexibility

## Refactoring Checklist

Before considering refactoring complete, ensure:
- [ ] All tests pass
- [ ] Code is easier to read
- [ ] Code is easier to maintain
- [ ] No functionality was broken
- [ ] Performance is not degraded
- [ ] Security vulnerabilities are fixed
- [ ] Error handling is proper
- [ ] Code follows PSR standards
