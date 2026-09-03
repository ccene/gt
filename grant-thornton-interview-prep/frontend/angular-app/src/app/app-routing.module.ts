import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { OrderListComponent } from './components/order-list/order-list.component';
import { OrderDetailComponent } from './components/order-detail/order-detail.component';
import { OrderFormComponent } from './components/order-form/order-form.component';

const routes: Routes = [
  { path: 'orders', component: OrderListComponent },
  { path: 'orders/new', component: OrderFormComponent },
  { path: 'orders/:id', component: OrderDetailComponent },
  { path: '', redirectTo: '/orders', pathMatch: 'full' },
  { path: '**', redirectTo: '/orders' }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
