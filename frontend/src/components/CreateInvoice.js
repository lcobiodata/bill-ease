import React, { useEffect, useState } from "react";
import {
  TextField,
  Button,
  Container,
  Paper,
  Typography,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Box,
  CircularProgress,
  Alert
} from "@mui/material";
import { useNavigate } from "react-router-dom";

const API_URL = process.env.REACT_APP_API_URL; 

const CreateInvoice = () => {
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const [clients, setClients] = useState([]);
  const [invoice, setInvoice] = useState({
    client_id: "",
    issue_date: "",
    due_date: "",
    subtotal: 0,
    tax_amount: 0,
    discount: 0,
    total_amount: 0,
    status: "Unpaid",
    payment_method: "",
    items: []
  });

  const [newItem, setNewItem] = useState({ description: "", quantity: "", rate: "", amount: "" });
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    const response = await fetch(`${API_URL}/clients`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    setClients(data);
  };

  const handleChange = (e) => {
    setInvoice({ ...invoice, [e.target.name]: e.target.value });
  };

  const handleItemChange = (e) => {
    setNewItem({ ...newItem, [e.target.name]: e.target.value });
  };

  const addItem = () => {
    const itemAmount = parseFloat(newItem.quantity || 0) * parseFloat(newItem.rate || 0);
    const updatedItems = [...invoice.items, { ...newItem, amount: itemAmount }];
    const newSubtotal = updatedItems.reduce((sum, item) => sum + item.amount, 0);
    const tax = parseFloat(invoice.tax_amount) || 0;
    const discount = parseFloat(invoice.discount) || 0;
    const newTotal = newSubtotal + tax - discount;
  
    setInvoice({ ...invoice, items: updatedItems, subtotal: newSubtotal, total_amount: newTotal });
  
    // Reset item fields to be completely empty instead of 1 or 0
    setNewItem({ description: "", quantity: "", rate: "", amount: "" });
  };
  

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsRedirecting(true);

    try {
      const response = await fetch(`${API_URL}/invoice`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(invoice),
      });

      if (!response.ok) throw new Error("Failed to create invoice.");

      setMessage(<Alert severity="success">Invoice created successfully! Redirecting...</Alert>);

      // ⏳ Wait for 2 seconds before redirecting
      setTimeout(() => navigate("/dashboard"), 2000);
    } catch (error) {
      setMessage(<Alert severity="error">Failed to create invoice. Please try again.</Alert>);
      setIsRedirecting(false);
    }
  };

  return (
    <Container maxWidth="md">
      <Paper elevation={3} sx={{ p: 4, mt: 5 }}>
        <Typography variant="h5" gutterBottom>Create Invoice</Typography>

        {/* Show success or error message */}
        {message && <Box sx={{ my: 2 }}>{message}</Box>}

        {isRedirecting ? (
          <Box sx={{ display: "flex", justifyContent: "center", mt: 5 }}>
            <CircularProgress size={40} />
          </Box>
        ) : (
          <>
            <TextField
              select
              label="Select Client"
              name="client_id"
              fullWidth
              margin="normal"
              value={invoice.client_id}
              onChange={handleChange}
            >
              {clients.map((client) => (
                <MenuItem key={client.id} value={client.id}>
                  {client.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField label="Issue Date" type="date" name="issue_date" fullWidth margin="normal" onChange={handleChange} InputLabelProps={{ shrink: true }} />
            <TextField label="Due Date" type="date" name="due_date" fullWidth margin="normal" onChange={handleChange} InputLabelProps={{ shrink: true }} />
            <TextField label="Tax Amount" type="number" name="tax_amount" fullWidth margin="normal" onChange={handleChange} />
            <TextField label="Discount" type="number" name="discount" fullWidth margin="normal" onChange={handleChange} />
            <TextField select label="Payment Method" name="payment_method" fullWidth margin="normal" value={invoice.payment_method} onChange={handleChange}>
              <MenuItem value="Cash">Cash</MenuItem>
              <MenuItem value="Credit Card">Credit Card</MenuItem>
              <MenuItem value="PayPal">PayPal</MenuItem>
              <MenuItem value="Bank Transfer">Bank Transfer</MenuItem>
            </TextField>
            
            <Typography variant="h6" sx={{ mt: 3 }}>Invoice Items</Typography>
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Description</TableCell>
                    <TableCell>Quantity</TableCell>
                    <TableCell>Rate</TableCell>
                    <TableCell>Amount</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {invoice.items.map((item, index) => (
                    <TableRow key={index}>
                      <TableCell>{item.description}</TableCell>
                      <TableCell>{item.quantity}</TableCell>
                      <TableCell>{item.rate}</TableCell>
                      <TableCell>{item.amount}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            {/* Item Input Fields */}
            <TextField label="Description" name="description" fullWidth margin="normal" value={newItem.description} onChange={handleItemChange} />
            <TextField label="Quantity" type="number" name="quantity" fullWidth margin="normal" value={newItem.quantity} onChange={handleItemChange} />
            <TextField label="Rate" type="number" name="rate" fullWidth margin="normal" value={newItem.rate} onChange={handleItemChange} />

            {/* Buttons */}
            <Box sx={{ display: "flex", justifyContent: "flex-start", mt: 3 }}>
              <Button variant="contained" color="primary" onClick={addItem}>Add Item</Button>
            </Box>
            <Box sx={{ display: "flex", justifyContent: "center", mt: 5 }}>
              <Button variant="contained" color="secondary" onClick={handleSubmit} disabled={isRedirecting}>
                {isRedirecting ? <CircularProgress size={24} /> : "Submit Invoice"}
              </Button>
            </Box>
          </>
        )}
      </Paper>
    </Container>
  );
};

export default CreateInvoice;
