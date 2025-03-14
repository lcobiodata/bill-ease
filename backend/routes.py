from flask import Blueprint, request, jsonify, redirect, current_app as app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from flask_bcrypt import Bcrypt
import secrets
import google.auth.transport.requests
import google.oauth2.id_token

from models import db, User, Client, Invoice, InvoiceItem, PaymentMethod, InvoiceStatus, Currency, InvoiceUnit
from flask_mail import Message, Mail
from config import Config
from datetime import datetime

bcrypt = Bcrypt()
mail = Mail()

# Create Blueprint for routes
routes_bp = Blueprint("routes", __name__)

# -------------------- Helper Functions --------------------
def send_verification_email(email: str, token: str):
    """
    Sends an email with a verification link that redirects to the React frontend.
    """
    verification_link = f"{Config.PREFERRED_URL_SCHEME}://{Config.SERVER_NAME}/verify/{token}"

    msg = Message(
        subject="Verify Your FreelanceBill Account",
        recipients=[email],
        body=f"Please click the link below to verify your account:\n{verification_link}\n\n"
             f"If you did not register, you can safely ignore this email."
    )

    mail.send(msg)

def send_password_recovery_email(email: str, token: str):
    """
    Sends a password recovery email with a reset link to the React frontend.
    """
    reset_link = f"{Config.FRONTEND_URL}/reset-password/{token}"  # Redirects to React

    msg = Message(
        subject="Reset Your FreelanceBill Password",
        recipients=[email],
        body=f"To reset your password, please click the link below:\n{reset_link}\n\n"
             f"If you did not request a password reset, you can safely ignore this email."
    )

    mail.send(msg)

# -------------------- Authentication Routes --------------------
@routes_bp.route("/register", methods=["POST"])
def register():
    """
    Registers a new user. Generates a verification token and sends an email
    with the link to verify.
    """
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    name = data.get("name")
    business_name = data.get("business_name")
    email = data.get("email")
    phone = data.get("phone")
    address = data.get("address")
    tax_number = data.get("tax_number")

    # Check if user exists
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "User already exists"}), 400

    # Hash password
    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

    # Generate a token for verification
    verification_token = secrets.token_urlsafe(32)

    # Create the new user with is_verified=False
    new_user = User(
        username=username,
        password=hashed_password,
        is_verified=False,
        verification_token=verification_token,
        name=name,
        business_name=business_name,
        email=email,
        phone=phone,
        address=address,
        tax_number=tax_number
    )
    db.session.add(new_user)
    db.session.commit()

    # Send a verification email
    send_verification_email(email, verification_token)

    return jsonify({"message": "User registered. Please check your email to verify."}), 201


@routes_bp.route("/verify/<token>", methods=["GET"])
def verify_email(token):
    """
    Verifies the user's email address if the token matches.
    """
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        return jsonify({"message": "Invalid verification token."}), 400

    # Mark the user as verified
    user.is_verified = True
    user.verification_token = None
    db.session.commit()

    # Redirect to the frontend verification success page
    return redirect(f'{Config.FRONTEND_URL}/verify-success', code=302)


@routes_bp.route("/login", methods=["POST"])
def login():
    """
    Traditional login route. Checks if user is verified before issuing JWT.
    """
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"message": "Invalid credentials"}), 401

    # OPTIONAL: If you want to enforce verification:
    if not user.is_verified:
        return jsonify({"message": "Email not verified. Please check your inbox."}), 403

    if not bcrypt.check_password_hash(user.password, password):
        return jsonify({"message": "Invalid credentials"}), 401

    access_token = create_access_token(identity=username)
    return jsonify({"token": access_token}), 200


@routes_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    """
    Change password route. Requires JWT for authentication.
    """
    data = request.get_json()
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return jsonify({"message": "Current password and new password are required"}), 400

    current_user = get_jwt_identity()
    user = User.query.filter_by(username=current_user).first()

    if not bcrypt.check_password_hash(user.password, current_password):
        return jsonify({"message": "Current password is incorrect"}), 401

    hashed_new_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    user.password = hashed_new_password
    db.session.commit()

    return jsonify({"message": "Password changed successfully"}), 200


@routes_bp.route("/recover-password", methods=["POST"])
def recover_password():
    """
    Sends a password recovery email with a link to the React reset password page.
    """
    data = request.get_json()
    email = data.get("email")

    user = User.query.filter_by(username=email).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Generate a password reset token
    recovery_token = secrets.token_urlsafe(32)
    user.verification_token = recovery_token
    db.session.commit()

    # Send the password recovery email with a React frontend link
    send_password_recovery_email(email, recovery_token)

    return jsonify({"message": "Password recovery email sent. Please check your inbox."}), 200

@routes_bp.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    """
    Resets the user's password if the token matches.
    """
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        return jsonify({"message": "Invalid or expired token."}), 400

    data = request.get_json()
    new_password = data.get("new_password")
    confirm_password = data.get("confirm_password")

    if not new_password or not confirm_password:
        return jsonify({"message": "Both password fields are required."}), 400

    if new_password != confirm_password:
        return jsonify({"message": "Passwords do not match."}), 400

    # Hash the new password and update the user
    hashed_new_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    user.password = hashed_new_password
    user.verification_token = None  # Clear the token after successful reset
    db.session.commit()

    return jsonify({"message": "Password reset successful. You can now log in."}), 200

@routes_bp.route("/login/google", methods=["POST"])
def login_google():
    """
    Client-side Google OAuth login flow.
    Expects JSON payload: {"token": "<Google ID token>"}
    """
    data = request.get_json()
    if not data or "token" not in data:
        return jsonify({"error": "No token provided"}), 400

    id_token_str = data["token"]
    try:
        # Verify the token using google-auth
        id_info = google.oauth2.id_token.verify_oauth2_token(
            id_token_str,
            google.auth.transport.requests.Request(),
            Config.GOOGLE_CLIENT_ID
        )
        # Extract user information from the ID token
        email = id_info.get("email")
        name = id_info.get("name")

        if not email:
            return jsonify({"error": "Email not provided by Google"}), 400

        # Create or fetch the user, mark as verified automatically (since Google verified)
        user = User.query.filter_by(username=email).first()
        if not user:
            user = User(
                username=email,
                password=None,
                is_verified=True,
                name=name,
                email=email,
            )
            db.session.add(user)
            db.session.commit()

        # Generate our own JWT for the user
        access_token = create_access_token(identity=email)
        return jsonify({"token": access_token, "user": {"email": email, "name": name}}), 200

    except ValueError:
        # Token verification failed
        return jsonify({"error": "Invalid or expired ID token"}), 401


@routes_bp.route("/update-email", methods=["POST"])
@jwt_required()
def update_email():
    """
    Update email route. Requires JWT for authentication.
    """
    data = request.get_json()
    new_email = data.get("new_email")

    if not new_email:
        return jsonify({"message": "New email is required"}), 400

    current_user = get_jwt_identity()
    user = User.query.filter_by(username=current_user).first()

    if User.query.filter_by(username=new_email).first():
        return jsonify({"message": "Email already in use"}), 400

    user.username = new_email
    user.is_verified = False  # Mark the new email as unverified
    verification_token = secrets.token_urlsafe(32)
    user.verification_token = verification_token
    db.session.commit()

    # Send a verification email to the new email address
    send_verification_email(new_email, verification_token)

    return jsonify({"message": "Email updated successfully. Please verify your new email."}), 200

# -------------------- Client Routes --------------------
@routes_bp.route("/clients", methods=["GET"])
@jwt_required()
def get_clients():
    """ Fetch all clients for the authenticated user """
    current_user = get_jwt_identity()
    clients = Client.query.join(User).filter(User.username == current_user).all()

    return jsonify([{
        "id": client.id,
        "name": client.name,
        "business_name": client.business_name,
        "email": client.email,
        "phone": client.phone,
        "address": client.address
    } for client in clients]), 200

@routes_bp.route("/client", methods=["POST"])
@jwt_required()
def create_client():
    """ Create a new client """
    data = request.get_json()
    name = data.get("name")
    business_name = data.get("business_name")
    email = data.get("email")
    phone = data.get("phone")
    address = data.get("address")

    current_user = get_jwt_identity()
    user_id = User.query.filter_by(username=current_user).first().id

    client = Client(
        user_id=user_id,
        name=name,
        business_name=business_name,
        email=email,
        phone=phone,
        address=address
    )
    db.session.add(client)
    db.session.commit()
    return jsonify({"message": "Client created successfully", "client_id": client.id}), 201

@routes_bp.route("/clients/<int:client_id>", methods=["PUT"])
@jwt_required()
def update_client(client_id):
    """ Update an existing client """
    data = request.get_json()
    
    # Get the logged-in user
    current_user = get_jwt_identity()
    user = User.query.filter_by(username=current_user).first()

    # Find the client by ID and ensure it belongs to the user
    client = Client.query.filter_by(id=client_id, user_id=user.id).first()

    if not client:
        return jsonify({"message": "Client not found"}), 404

    # Update the fields if provided
    client.name = data.get("name", client.name)
    client.business_name = data.get("business_name", client.business_name)
    client.email = data.get("email", client.email)
    client.phone = data.get("phone", client.phone)
    client.address = data.get("address", client.address)

    db.session.commit()

    return jsonify({"message": "Client updated successfully"}), 200

# -------------------- Invoice Routes --------------------
from sqlalchemy.orm import joinedload
from sqlalchemy import func

@routes_bp.route("/invoices", methods=["GET"])
@jwt_required()
def get_invoices():
    """ Fetch all invoices for the authenticated user with optimized joins """
    current_user = get_jwt_identity()

    # Query all invoices for the user joined with the client
    invoices = Invoice.query.join(User).filter(User.username == current_user).options(joinedload(Invoice.client)).all()

    # Check due date and update status in the database if overdue
    today = datetime.today().date()
    for inv in invoices:
        # Determine if the invoice is overdue
        if inv.due_date < today and inv.status == InvoiceStatus.UNPAID:
            inv.status = InvoiceStatus.OVERDUE
        
    # Commit the changes to the database
    db.session.commit()

    # Query again to ensure changes are reflected
    invoices = Invoice.query.join(User).filter(User.username == current_user).options(joinedload(Invoice.client)).all()
    
    # Build the response data
    invoices_data = []
    for inv in invoices:
        items = InvoiceItem.query.filter_by(invoice_id=inv.id).all()
        invoices_data.append({
            "invoice_number": inv.invoice_number,
            "client": inv.client.name if inv.client else "Unknown",
            "issue_date": inv.issue_date.strftime("%Y-%m-%d"),
            "due_date": inv.due_date.strftime("%Y-%m-%d"),
            "currency": inv.currency.name,
            "tax_rate": inv.tax_rate,
            "subtotal": inv.subtotal,
            "total_discount": inv.total_discount,
            "tax_amount": inv.tax_amount,
            "total_amount": inv.total_amount,
            "status": inv.status.value,  # Convert enum to string
            "payment_method": inv.payment_method.value,  # Convert enum to string
            "payment_date": inv.payment_date.strftime("%Y-%m-%d") if inv.payment_date else None,
            "items": [{
                "id": item.id,
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit.name,
                "rate": item.rate,
                "discount": item.discount,
                "gross_amount": item.gross_amount,
                "net_amount": item.net_amount
            } for item in items]
        })

    return jsonify(invoices_data), 200


@routes_bp.route("/invoice", methods=["POST"])
@jwt_required()
def create_invoice():
    """Create a new invoice with line items"""
    data = request.get_json()

    # Extract and validate required fields
    required_fields = ["client_id", "issue_date", "due_date", "currency", "payment_method"]
    if any(field not in data or not data[field] for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        issue_date = datetime.strptime(data["issue_date"], "%Y-%m-%d").date()
        due_date = datetime.strptime(data["due_date"], "%Y-%m-%d").date()
        if due_date < issue_date:
            return jsonify({"error": "Due date cannot be before issue date"}), 400
    except ValueError:
        return jsonify({"error": "Invalid date format (expected YYYY-MM-DD)"}), 400

    # Validate enums
    currency_code = data["currency"].upper()
    currency = getattr(Currency, currency_code, None)
    if not currency:
        return jsonify({"error": f"Invalid currency '{currency_code}'"}), 400

    status = data.get("status", "Unpaid").upper()
    if status not in InvoiceStatus.__members__:
        return jsonify({"error": f"Invalid status '{status}'"}), 400
    status_enum = InvoiceStatus[status]

    payment_method_value = data["payment_method"].strip()
    payment_method = next((pm for pm in PaymentMethod if pm.value == payment_method_value), None)
    if not payment_method:
        return jsonify({"error": f"Invalid payment method '{payment_method_value}'"}), 400

    # Validate user
    current_user = get_jwt_identity()
    user = User.query.filter_by(username=current_user).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Validate client
    client = Client.query.get(data["client_id"])
    if not client:
        return jsonify({"error": "Client not found"}), 404

    # Generate invoice number
    last_invoice = Invoice.query.filter_by(user_id=user.id).order_by(Invoice.id.desc()).first()
    invoice_number = str(int(last_invoice.invoice_number) + 1) if last_invoice else "1"

    # Compute invoice totals
    items = data.get("items", [])
    subtotal, total_discount = 0.0, 0.0

    for item in items:
        try:
            quantity = float(item["quantity"])
            rate = float(item["rate"])
            discount = float(item.get("discount", 0.0))
        except (ValueError, TypeError):
            return jsonify({"error": f"Invalid numeric values in items"}), 400

        gross_amount = quantity * rate
        net_amount = gross_amount * (1 - discount / 100)

        subtotal += gross_amount
        total_discount += gross_amount * (discount / 100)

    discounted_price = subtotal - total_discount
    tax_rate = float(data.get("tax_rate", 0.0) or 0.0)

    tax_amount = (tax_rate / 100) * discounted_price
    total_amount = discounted_price + tax_amount

    # Create Invoice
    invoice = Invoice(
        invoice_number=invoice_number,
        user_id=user.id,
        client_id=client.id,
        issue_date=issue_date,
        due_date=due_date,
        currency=currency,
        tax_rate=tax_rate,
        subtotal=subtotal,
        total_discount=total_discount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status=status_enum,
        payment_method=payment_method,
        payment_date=None,
    )
    db.session.add(invoice)
    db.session.flush()  # Ensure invoice ID is available before adding items

    # Create Invoice Items
    for item in items:
        unit_key = item.get("unit")
        if unit_key not in InvoiceUnit.__members__:
            return jsonify({"error": f"Invalid or missing unit '{unit_key}'"}), 400

        unit_enum = InvoiceUnit[unit_key]
        gross_amount = float(item["quantity"]) * float(item["rate"])
        net_amount = gross_amount * (1 - float(item.get("discount", 0.0)) / 100)

        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            quantity=float(item["quantity"]),
            unit=unit_enum,
            description=item["description"],
            rate=float(item["rate"]),
            discount=float(item.get("discount", 0.0)),
            gross_amount=gross_amount,
            net_amount=net_amount,
        )
        db.session.add(invoice_item)

    db.session.commit()
    return jsonify({"message": "Invoice created successfully", "invoice_id": invoice.id}), 201

@routes_bp.route("/invoice/<int:invoice_id>", methods=["GET"])
@jwt_required()
def get_invoice(invoice_id):
    """ Fetch a single invoice by ID """
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return jsonify({"message": "Invoice not found"}), 404
    
    # Check due date and update status if overdue
    today = datetime.today().date()
    if invoice.due_date < today and invoice.status == InvoiceStatus.UNPAID:
        invoice.status = InvoiceStatus.OVERDUE
        db.session.commit()
    
    # Query again to ensure changes are reflected
    invoice = Invoice.query.get(invoice_id)

    # Query the items for the invoice
    items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()

    return jsonify({
        "invoice_number": invoice.invoice_number,
        "client": invoice.client.name if invoice.client else "Unknown",
        "issue_date": invoice.issue_date.strftime("%Y-%m-%d"),
        "due_date": invoice.due_date.strftime("%Y-%m-%d"),
        "currency": invoice.currency.name,
        "tax": invoice.tax,
        "status": invoice.status.value,  # Convert enum to string
        "payment_method": invoice.payment_method.value,  # Convert enum to string
        "payment_date": invoice.payment_date.strftime("%Y-%m-%d") if invoice.payment_date else None,
        "items": [{
            "id": item.id,
            "description": item.description,
            "quantity": item.quantity,
            "unit": item.unit.name,
            "rate": item.rate,
            "discount": item.discount
        } for item in items]
    }), 200

@routes_bp.route("/invoice/<int:invoice_id>/items", methods=["POST"])
@jwt_required()
def add_invoice_item(invoice_id):
    """ Add an item to an existing invoice """
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return jsonify({"message": "Invoice not found"}), 404

    data = request.get_json()
    invoice_item = InvoiceItem(
        invoice_id=invoice_id,
        description=data.get("description"),
        quantity=float(data.get("quantity")),
        unit=InvoiceUnit[data.get("unit")],
        rate=float(data.get("rate")),
        discount=float(data.get("discount", 0.0))
    )

    db.session.add(invoice_item)
    db.session.commit()
    return jsonify({"message": "Item added successfully"}), 201

@routes_bp.route("/invoice/item/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_invoice_item(item_id):
    """ Delete an invoice item """
    item = InvoiceItem.query.get(item_id)
    if not item:
        return jsonify({"message": "Item not found"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Item deleted successfully"}), 200

# -------------------- Payment Tracking --------------------
@routes_bp.route("/invoice/<int:invoice_id>/mark-paid", methods=["POST"])
@jwt_required()
def mark_invoice_paid(invoice_id):
    """ Mark an invoice as paid """
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return jsonify({"message": "Invoice not found"}), 404
    # invoice.status = "Paid"
    invoice.status = InvoiceStatus.PAID
    invoice.payment_date = datetime.now().date()
    db.session.commit()
    return jsonify({"message": "Invoice marked as paid"}), 200

@routes_bp.route("/invoice/<int:invoice_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_invoice(invoice_id):
    """ Cancel an invoice """
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return jsonify({"message": "Invoice not found"}), 404

    # Check if the invoice is already paid
    if invoice.status == InvoiceStatus.PAID:
        return jsonify({"message": "Cannot cancel a paid invoice"}), 400

    # Allow cancellation only if the invoice is unpaid or overdue
    if invoice.status in [InvoiceStatus.UNPAID, InvoiceStatus.OVERDUE]:
        invoice.status = InvoiceStatus.CANCELLED
        db.session.commit()
        return jsonify({"message": "Invoice cancelled"}), 200

    return jsonify({"message": "Invoice cannot be cancelled"}), 400