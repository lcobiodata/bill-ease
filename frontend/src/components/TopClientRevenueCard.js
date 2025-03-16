import React from "react";
import { Card, CardContent, Typography } from "@mui/material";

const TopClientRevenueCard = ({ client }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" color="textSecondary" gutterBottom>
          Top Client (Revenue)
        </Typography>
        <Typography variant="h4">
          {client ? client.name : "N/A"}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          {client ? `$${client.totalRevenue.toFixed(2)} revenue` : ""}
        </Typography>
      </CardContent>
    </Card>
  );
};

export default TopClientRevenueCard;
